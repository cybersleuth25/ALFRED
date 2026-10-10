import importlib.util
import os
import sys
import time
import types
from unittest.mock import MagicMock

import pytest

import shared
from tools import core_tools, developer_tools


# ── Event bus fan-out ──

def test_broadcaster_delivers_every_event_to_every_subscriber():
    bus = shared.EventBroadcaster()
    a, b = bus.subscribe(), bus.subscribe()
    bus.put({"type": "state", "value": "idle"})
    assert a.get_nowait() == {"type": "state", "value": "idle"}
    assert b.get_nowait() == {"type": "state", "value": "idle"}

    bus.unsubscribe(a)
    bus.put({"type": "state", "value": "speaking"})
    assert a.empty()
    assert b.get_nowait()["value"] == "speaking"


def test_broadcaster_drops_oldest_when_subscriber_is_full():
    bus = shared.EventBroadcaster(maxsize=2)
    q = bus.subscribe()
    for i in range(3):
        bus.put(i)
    assert [q.get_nowait(), q.get_nowait()] == [1, 2]


# ── Confirmation gate for dangerous tools ──

@pytest.fixture
def gated_tool(monkeypatch):
    calls = []
    monkeypatch.setitem(core_tools.TOOL_REGISTRY, "run_terminal_command",
                        lambda command, cwd="": calls.append(command) or f"ran {command}")
    monkeypatch.setattr(core_tools, "_pending_action", None)
    return calls


def test_gated_tool_does_not_run_without_confirmation(gated_tool):
    res = core_tools.execute_tool("run_terminal_command", {"command": "echo hi"})
    assert res.startswith("CONFIRMATION REQUIRED")
    assert gated_tool == []
    assert core_tools.has_pending_action()


def test_confirm_runs_pending_tool_once(gated_tool):
    core_tools.execute_tool("run_terminal_command", {"command": "echo hi"})
    assert core_tools.handle_confirmation_reply("Confirm.") == "ran echo hi"
    assert gated_tool == ["echo hi"]
    assert core_tools.handle_confirmation_reply("confirm") is None  # not replayable


def test_cancel_discards_pending_tool(gated_tool):
    core_tools.execute_tool("run_terminal_command", {"command": "echo hi"})
    assert core_tools.handle_confirmation_reply("cancel").startswith("Cancelled")
    assert gated_tool == []
    assert not core_tools.has_pending_action()


def test_unrelated_reply_leaves_action_pending(gated_tool):
    core_tools.execute_tool("run_terminal_command", {"command": "echo hi"})
    assert core_tools.handle_confirmation_reply("what's the weather") is None
    assert core_tools.has_pending_action()


def test_pending_action_expires(gated_tool, monkeypatch):
    core_tools.execute_tool("run_terminal_command", {"command": "echo hi"})
    real_time = time.time
    monkeypatch.setattr(core_tools.time, "time", lambda: real_time() + 10_000)
    assert core_tools.handle_confirmation_reply("confirm") is None
    assert gated_tool == []


def test_safe_tool_runs_immediately(monkeypatch):
    monkeypatch.setitem(core_tools.TOOL_REGISTRY, "get_battery_status", lambda: "90%")
    assert core_tools.execute_tool("get_battery_status", {}) == "90%"


# ── Terminal backstop patterns ──

@pytest.mark.parametrize("cmd", [
    "format c:", "diskpart", "rd /s /q C:\\", "Remove-Item -Recurse -Force $env:USERPROFILE",
    "dd if=/dev/zero of=/dev/sda", "echo x && format d: /q",
])
def test_catastrophic_commands_blocked(cmd):
    assert developer_tools._is_blocked_command(cmd)


@pytest.mark.parametrize("cmd", [
    "git log --format=%H -n 1", "npm run build", "python -m pytest -q", "del build\\out.txt",
])
def test_normal_commands_allowed(cmd):
    assert not developer_tools._is_blocked_command(cmd)


# ── Web API guard ──

@pytest.fixture(scope="module")
def web_app():
    # web/app.py imports the full voice/vision runtime via `alfred`; stub it out.
    saved = sys.modules.get("alfred")
    sys.modules["alfred"] = types.SimpleNamespace(main_loop=lambda: None)
    try:
        path = os.path.join(os.path.dirname(__file__), "..", "web", "app.py")
        spec = importlib.util.spec_from_file_location("alfred_web_app", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        yield module
    finally:
        if saved is None:
            sys.modules.pop("alfred", None)
        else:
            sys.modules["alfred"] = saved


@pytest.fixture
def client(web_app):
    from fastapi.testclient import TestClient
    return TestClient(web_app.app)


def test_post_without_token_is_rejected(client):
    assert client.post("/api/incidents/clear").status_code == 403


def test_text_plain_csrf_to_command_is_rejected(client):
    res = client.post("/api/command", content='{"command": "run calc"}',
                      headers={"Content-Type": "text/plain", "Origin": "https://evil.example"})
    assert res.status_code == 403


def test_post_with_token_is_accepted(client, web_app):
    res = client.post("/api/incidents/clear", headers={"X-Alfred-Token": web_app.SESSION_TOKEN})
    assert res.status_code == 200


def test_foreign_host_is_rejected(client):
    # DNS rebinding: attacker domain resolving to 127.0.0.1
    assert client.get("/api/session-token", headers={"Host": "attacker.example:8000"}).status_code == 403


def test_session_token_not_readable_cross_origin(client):
    res = client.get("/api/session-token", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in res.headers


def test_session_token_readable_by_hud_origin(client, web_app):
    res = client.get("/api/session-token", headers={"Origin": "http://localhost:5173"})
    assert res.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert res.json()["token"] == web_app.SESSION_TOKEN


def test_command_endpoint_runs_with_token(client, web_app, monkeypatch):
    import llm_engine
    import persona_engine
    persona = types.SimpleNamespace(display_name="Alfred")
    monkeypatch.setattr(llm_engine, "generate_response", MagicMock(return_value="Very good, sir."))
    monkeypatch.setattr(persona_engine, "get_active_persona", lambda: persona)
    monkeypatch.setattr(persona_engine, "extract_persona_name", lambda text: None)
    monkeypatch.setitem(sys.modules, "voice_engine", types.SimpleNamespace(speak=lambda text: None))

    res = client.post("/api/command", json={"command": "status report"},
                      headers={"X-Alfred-Token": web_app.SESSION_TOKEN})
    assert res.status_code == 200
    assert res.json()["reply"] == "Very good, sir."


def test_lockdown_route_registered_once(web_app):
    routes = [r for r in web_app.app.routes if getattr(r, "path", "") == "/api/focus/lockdown"]
    assert len(routes) == 1


def test_generate_response_handles_confirmation(gated_tool):
    import llm_engine
    core_tools.execute_tool("run_terminal_command", {"command": "echo hi"})
    assert llm_engine.generate_response("confirm") == "ran echo hi"
    assert gated_tool == ["echo hi"]
