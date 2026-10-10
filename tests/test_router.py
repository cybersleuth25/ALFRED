import pytest
import sys
import types
from unittest.mock import MagicMock
import shared
import llm_engine

@pytest.fixture(autouse=True)
def mock_router_dependencies(monkeypatch):
    """Mocks external system interactions like core tool execution and focus daemon control."""
    # 1. Mock core_tools.execute_tool
    mock_execute_tool = MagicMock(return_value="Mocked tool execution successful")
    monkeypatch.setattr(llm_engine.core_tools, "execute_tool", mock_execute_tool)

    # 2. Stub the lazily imported study_mentor module.  Loading the real module
    # starts the voice stack, which is irrelevant to routing tests and makes
    # collection needlessly slow.
    mock_activate = MagicMock(return_value="Focus Mode activated (mocked).")
    mock_deactivate = MagicMock(return_value="Focus Mode deactivated (mocked).")
    mock_is_active = MagicMock(return_value=False)
    mock_study_mentor = types.ModuleType("study_mentor")
    mock_study_mentor.activate = mock_activate
    mock_study_mentor.deactivate = mock_deactivate
    mock_study_mentor.is_active = mock_is_active
    monkeypatch.setitem(sys.modules, "study_mentor", mock_study_mentor)

    test_persona = types.SimpleNamespace(
        name="alfred",
        display_name="Alfred",
        honorific="sir",
        personality_prompt="",
        get_title=lambda user_name: f"Master {user_name}",
    )
    monkeypatch.setattr(llm_engine.persona_engine, "get_active_persona", lambda: test_persona)

    # Clean shared state variables
    shared.awaiting_study_confirmation = False
    shared.focus_mode_active = False

    return {
        "execute_tool": mock_execute_tool,
        "activate": mock_activate,
        "deactivate": mock_deactivate,
        "is_active": mock_is_active
    }


def test_canned_greetings():
    """Verify that greetings trigger instant zero-LLM canned responses."""
    resp = llm_engine.generate_response("hello")
    assert resp.startswith(("Hey", "Hello"))

    resp_time = llm_engine.generate_response("what time is it")
    assert "sir" in resp_time
    assert ":" in resp_time


def test_focus_mode_lifecycle(mock_router_dependencies):
    """Test start focus mode intent, confirmation (yes/no), and stop focus mode."""
    # 1. Prompt to start focus mode -> should set confirmation state
    resp = llm_engine.generate_response("start focus mode")
    assert "Shall I initiate Protocol Omega" in resp
    assert shared.awaiting_study_confirmation is True

    # 2. Say yes to confirm Focus Mode initiation
    resp_yes = llm_engine.generate_response("yes")
    assert "Focus Mode activated" in resp_yes
    assert shared.awaiting_study_confirmation is False
    mock_router_dependencies["activate"].assert_called_once()

    # 3. Requesting stop when focus mode is not active
    mock_router_dependencies["is_active"].return_value = False
    resp_stop_inactive = llm_engine.generate_response("stop focus mode")
    assert "Protocol Omega is not currently active" in resp_stop_inactive

    # 4. Requesting stop when focus mode is active
    mock_router_dependencies["is_active"].return_value = True
    resp_stop_active = llm_engine.generate_response("stop focus mode")
    assert "Focus Mode deactivated" in resp_stop_active
    mock_router_dependencies["deactivate"].assert_called_once()


def test_app_and_music_triggers(mock_router_dependencies):
    """Verify that launching apps and playing music trigger core tools."""
    # Launch app
    resp_app = llm_engine.generate_response("open spotify")
    assert "Opening spotify" in resp_app
    mock_router_dependencies["execute_tool"].assert_any_call("launch_application", {"app_name": "spotify"})

    # Play song
    resp_song = llm_engine.generate_response("play believer")
    assert "Playing believer" in resp_song
    mock_router_dependencies["execute_tool"].assert_any_call("play_music", {"song_query": "believer"}) # Split text splits to the query

    # Compound launcher
    resp_compound = llm_engine.generate_response("open notepad and play believer by imagine dragons")
    assert "Opening notepad" in resp_compound
    assert "playing believer by imagine dragons" in resp_compound
    mock_router_dependencies["execute_tool"].assert_any_call("launch_application", {"app_name": "notepad"})
    mock_router_dependencies["execute_tool"].assert_any_call("play_music", {"song_query": "believer by imagine dragons"})


def test_spotify_playback_controls(mock_router_dependencies):
    """Verify standard Spotify control shortcuts."""
    resp_pause = llm_engine.generate_response("pause music")
    assert "paused" in resp_pause
    mock_router_dependencies["execute_tool"].assert_any_call("spotify_pause", {})

    resp_resume = llm_engine.generate_response("resume playback")
    assert "playback" in resp_resume
    mock_router_dependencies["execute_tool"].assert_any_call("spotify_resume", {})

    resp_skip = llm_engine.generate_response("skip song")
    assert "Skipping" in resp_skip
    mock_router_dependencies["execute_tool"].assert_any_call("spotify_skip", {})


def test_reminders_and_os_controls(mock_router_dependencies):
    """Verify reminder set-up and direct OS shutdown/sleep controls."""
    # Reminder
    resp_remind = llm_engine.generate_response("remind me to drink water in 15 min")
    assert "remind you to drink water in 15 minutes" in resp_remind
    mock_router_dependencies["execute_tool"].assert_any_call("set_dynamic_reminder", {"minutes": 15, "topic": "drink water"})

    # Lock PC
    resp_lock = llm_engine.generate_response("lock my pc")
    assert "Done" in resp_lock
    mock_router_dependencies["execute_tool"].assert_any_call("lock_pc", {})


def test_network_and_brightness_controls(mock_router_dependencies):
    """Verify WiFi, Bluetooth, and brightness routing shortcuts."""
    # Brightness
    resp_bright = llm_engine.generate_response("set brightness to 70%")
    assert "Done" in resp_bright or "Right away" in resp_bright
    mock_router_dependencies["execute_tool"].assert_any_call("set_brightness", {"level": "70"})

    # WiFi disable
    resp_wifi = llm_engine.generate_response("turn off wifi")
    assert "Done" in resp_wifi
    mock_router_dependencies["execute_tool"].assert_any_call("toggle_wifi", {"action": "disable"})

    # Bluetooth enable
    resp_bt = llm_engine.generate_response("enable bluetooth")
    assert "Done" in resp_bt
    mock_router_dependencies["execute_tool"].assert_any_call("toggle_bluetooth", {"action": "enable"})


def test_fallback_to_agent_chat():
    """Verify that arbitrary conversational queries fall back to the multi-agent execution pipeline."""
    # This query doesn't match any canned/tool regex shortcuts, so it falls back to LLM
    resp = llm_engine.generate_response("write a song for me")
    # Should return our mocked response from conftest.py
    assert "Hello, I am a mock agent." in resp


def test_stock_and_face_search_routing(mock_router_dependencies):
    """Verify stock price, Chronos forecasting, and face search fast routing."""
    # Stock quote
    llm_engine.generate_response("stock price of reliance")
    mock_router_dependencies["execute_tool"].assert_any_call("get_stock_quote", {"symbol": "reliance"})

    # Stock forecast
    llm_engine.generate_response("forecast reliance for 14 days")
    mock_router_dependencies["execute_tool"].assert_any_call("forecast_stock", {"symbol": "reliance", "days": 14})

    # Reverse face search
    llm_engine.generate_response("reverse face search")
    mock_router_dependencies["execute_tool"].assert_any_call("reverse_face_search", {"image_path": "camera"})


# ── Table-driven routing pins ──
# Each row pins the exact tool call(s) a prompt produces today. A few rows
# document precedence quirks (e.g. the "tab" keyword shortcut winning over the
# close-tab regex) so a refactor cannot silently reorder the fast paths.
FAST_PATH_TOOL_CASES = [
    # Calendar (runs before keyword shortcuts)
    ("schedule a meeting with rahul tomorrow at 4 pm",
     [("create_calendar_event", {"title": "Meeting with Rahul", "start_time": "tomorrow at 4 pm"})]),
    ("what am i doing tomorrow", [("get_calendar_events", {"query_date": "tomorrow"})]),
    ("any plans next week", [("get_calendar_events", {"days": 7})]),
    ("what's on my calendar", [("get_calendar_events", {"query_date": "today"})]),
    # Keyword tool shortcuts
    ("what's the weather like", [("check_weather", {})]),
    ("read my journal", [("read_journal", {})]),
    ("close the youtube tab", [("list_browser_tabs", {})]),  # 'tab' shortcut wins
    # App launch / music
    ("open notepad", [("launch_application", {"app_name": "notepad"})]),
    ("start meeting", [("launch_application", {"app_name": "meeting"})]),  # 'start ' prefix wins
    ("play my favorites", [("play_user_daily_rotation", {})]),
    ("savan barse chalao", [("play_music", {"song_query": "savan barse"})]),
    ("gaana chalao", [("play_user_daily_rotation", {})]),
    ("play some music", [("play_music_by_mood", {})]),
    ("please play shape of you", [("play_music", {"song_query": "shape of you"})]),
    ("what's playing", [("get_now_playing", {})]),
    ("previous track", [("spotify_previous", {})]),
    # Messaging and reminders
    ("whatsapp mom saying hello there",
     [("send_whatsapp", {"contact_name": "mom", "message": "hello there"})]),
    ("list reminders", [("list_reminders", {})]),
    ("remind me in 2 hours to call dad", [("set_dynamic_reminder", {"minutes": 120, "topic": "call dad"})]),
    ("set a reminder in 5 min to stretch", [("set_dynamic_reminder", {"minutes": 5, "topic": "stretch"})]),
    ("add task finish homework", [("add_reminder", {"task": "finish homework"})]),
    # OS / developer
    ("take a screenshot", [("check_weather", {})]),  # quirk: 'hot' shortcut matches "screenshot"
    ("sleep mode", [("sleep_pc", {})]),
    ("cancel shutdown", [("cancel_shutdown", {})]),
    ("git status for all projects", [("git_status_diff", {"repo_path": "all"})]),
    ("git status list projects", [("git_status_diff", {"repo_path": "list"})]),
    ("scan secrets", [("scan_leaked_secrets", {})]),
    ("clean workspace", [("clean_dev_workspace", {})]),
    ("begin meeting", [("meeting_notetaker", {"action": "start"})]),
    ("end meeting", [("meeting_notetaker", {"action": "stop"})]),
    ("change brightness to 40", [("set_brightness", {"level": "40"})]),
    ("disconnect bluetooth", [("toggle_bluetooth", {"action": "disable"})]),
    ("switch to the github tab", [("list_browser_tabs", {})]),  # 'tab' shortcut wins
    # OSINT / market / research
    ("check instagram for natgeo", [("fetch_instagram_posts", {"username": "natgeo"})]),
    ("stock forecast tcs", [("forecast_stock", {"symbol": "tcs", "days": 14})]),
    ("share price of infosys", [("get_stock_quote", {"symbol": "infosys"})]),
    ("face search C:/pics/me.jpg", [("reverse_face_search", {"image_path": "C:/pics/me.jpg"})]),
    ("search for python decorators", [("search_web", {"query": "python decorators"})]),
    ("explain entropy from my notes", [("query_library", {"query": "explain entropy"})]),
    ("deep research on quantum computing", [("deep_research_swarm", {"topic": "quantum computing"})]),
    ("who invented the telephone", [("search_web", {"query": "who invented the telephone"})]),
]


@pytest.fixture
def stub_side_modules(monkeypatch):
    """Stubs lazily imported helper modules used by some fast paths."""
    import tools
    dev = types.ModuleType("tools.developer_tools")
    dev.discover_git_repositories = lambda: []
    monkeypatch.setitem(sys.modules, "tools.developer_tools", dev)
    monkeypatch.setattr(tools, "developer_tools", dev, raising=False)

    email = types.ModuleType("tools.email_tools")
    email.triage_inbox = lambda max_count=5: "Inbox triaged (mocked)."
    monkeypatch.setitem(sys.modules, "tools.email_tools", email)
    monkeypatch.setattr(tools, "email_tools", email, raising=False)

    cos = types.ModuleType("chief_of_staff")
    cos.get_spoken_chief_of_staff_briefing = lambda: "Dossier ready (mocked)."
    cos.get_quick_agenda = lambda day: f"Agenda for {day} (mocked)."
    monkeypatch.setitem(sys.modules, "chief_of_staff", cos)

    pushes = []
    monkeypatch.setattr(shared, "push_globe", lambda v: pushes.append(("globe", v)))
    monkeypatch.setattr(shared, "push_mirror_mode", lambda v: pushes.append(("mirror", v)))
    monkeypatch.setattr(llm_engine, "get_status_report", lambda: "Status report (mocked).")
    return pushes


@pytest.mark.parametrize("prompt,expected_calls", FAST_PATH_TOOL_CASES)
def test_fast_path_tool_routing(prompt, expected_calls, mock_router_dependencies, stub_side_modules):
    llm_engine.generate_response(prompt)
    calls = [(c.args[0], c.args[1]) for c in mock_router_dependencies["execute_tool"].call_args_list]
    assert calls == expected_calls


FAST_PATH_REPLY_CASES = [
    ("status report", "Status report (mocked).", None),
    ("show globe", "global intelligence view", ("globe", True)),
    ("hide map", "Returning to standard view", ("globe", False)),
    ("smart mirror", "Activating Smart Mirror", ("mirror", True)),
    ("exit mirror", "Deactivating Smart Mirror", ("mirror", False)),
    ("chief of staff", "Dossier ready (mocked).", None),
    ("daily agenda", "Agenda for today (mocked).", None),
    ("check my email", "Inbox triaged (mocked).", None),
    ("switch persona", "Which persona would you like", None),
]


@pytest.mark.parametrize("prompt,expected_text,expected_push", FAST_PATH_REPLY_CASES)
def test_fast_path_reply_routing(prompt, expected_text, expected_push, mock_router_dependencies, stub_side_modules):
    resp = llm_engine.generate_response(prompt)
    assert expected_text in resp
    mock_router_dependencies["execute_tool"].assert_not_called()
    assert stub_side_modules == ([expected_push] if expected_push else [])


def test_fast_path_speaks_progress_before_result(mock_router_dependencies, stub_side_modules):
    spoken = []
    llm_engine.generate_response("deep research on fusion", tts_callback=spoken.append)
    assert spoken[0].startswith("Deploying deep research swarm on fusion")
    assert spoken[-1] == "Mocked tool execution successful"


def test_knowledge_question_falls_through_when_search_fails(mock_router_dependencies):
    mock_router_dependencies["execute_tool"].return_value = "No web results found."
    resp = llm_engine.generate_response("why is the sky blue")
    mock_router_dependencies["execute_tool"].assert_called_once_with(
        "search_web", {"query": "why is the sky blue"})
    assert "Hello, I am a mock agent." in resp  # streamed chat path


def test_agent_loop_stops_on_confirmation_required(monkeypatch, mock_router_dependencies):
    replies = iter([
        '{"thought": "t", "tools_to_call": [{"tool": "delete_file", "kwargs": {"path": "a.txt"}}], "response": ""}',
        '{"thought": "t", "response": "Deleted it anyway."}',
    ])
    chat_calls = []

    def fake_chat(messages, **kwargs):
        chat_calls.append(messages)
        return {"message": {"content": next(replies)}}

    monkeypatch.setattr(llm_engine, "chat", fake_chat)
    mock_router_dependencies["execute_tool"].return_value = "CONFIRMATION REQUIRED: Delete a.txt? Say yes to proceed."
    resp = llm_engine.generate_response("delete the file report.txt")
    assert resp == "Delete a.txt? Say yes to proceed."
    assert len(chat_calls) == 1
    mock_router_dependencies["execute_tool"].assert_called_once_with("delete_file", {"path": "a.txt"})


def test_agent_loop_self_corrects_after_tool_error(monkeypatch, mock_router_dependencies):
    replies = iter([
        '{"thought": "t", "tools_to_call": [{"tool": "move_file", "kwargs": {}}], "response": "Done."}',
        '{"thought": "t", "tools_to_call": [], "response": "Fixed it."}',
    ])
    chat_calls = []

    def fake_chat(messages, **kwargs):
        chat_calls.append(list(messages))
        return {"message": {"content": next(replies)}}

    monkeypatch.setattr(llm_engine, "chat", fake_chat)
    mock_router_dependencies["execute_tool"].return_value = "Error: source not found"
    resp = llm_engine.generate_response("move the file notes.txt to documents")
    assert resp == "Fixed it."
    assert len(chat_calls) == 2
    assert chat_calls[1][-1]["content"].startswith("TOOL EXECUTION FAILED")
