import pytest
from unittest.mock import MagicMock
import shared
import llm_engine
import study_mentor

@pytest.fixture(autouse=True)
def mock_router_dependencies(monkeypatch):
    """Mocks external system interactions like core tool execution and focus daemon control."""
    # 1. Mock core_tools.execute_tool
    mock_execute_tool = MagicMock(return_value="Mocked tool execution successful")
    monkeypatch.setattr(llm_engine.core_tools, "execute_tool", mock_execute_tool)

    # 2. Mock study_mentor daemon controls to prevent side effects (pycaw volume, webcam, screen monitoring)
    mock_activate = MagicMock(return_value="Focus Mode activated (mocked).")
    mock_deactivate = MagicMock(return_value="Focus Mode deactivated (mocked).")
    mock_is_active = MagicMock(return_value=False)
    
    monkeypatch.setattr(study_mentor, "activate", mock_activate)
    monkeypatch.setattr(study_mentor, "deactivate", mock_deactivate)
    monkeypatch.setattr(study_mentor, "is_active", mock_is_active)

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
    assert any(greeting in resp for greeting in ["Good day", "Hello"])

    resp_time = llm_engine.generate_response("what time is it")
    assert "sir" in resp_time
    assert ":" in resp_time


def test_focus_mode_lifecycle(mock_router_dependencies):
    """Test start focus mode intent, confirmation (yes/no), and stop focus mode."""
    # 1. Prompt to start focus mode -> should set confirmation state
    resp = llm_engine.generate_response("start focus mode")
    assert "Shall I initiate Focus Mode" in resp
    assert shared.awaiting_study_confirmation is True

    # 2. Say yes to confirm Focus Mode initiation
    resp_yes = llm_engine.generate_response("yes")
    assert "Focus Mode activated" in resp_yes
    assert shared.awaiting_study_confirmation is False
    mock_router_dependencies["activate"].assert_called_once()

    # 3. Requesting stop when focus mode is not active
    mock_router_dependencies["is_active"].return_value = False
    resp_stop_inactive = llm_engine.generate_response("stop focus mode")
    assert "Focus Mode is not currently active" in resp_stop_inactive

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
    mock_router_dependencies["execute_tool"].assert_any_call("set_dynamic_reminder", {"minutes": "15", "topic": "drink water"})

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
