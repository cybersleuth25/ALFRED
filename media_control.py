"""
Media Controller for JARVIS / ALFRED.
=====================================
Direct hardware-level control of media playback (Spotify, YouTube, VLC, browser)
via Windows virtual keycodes (VK_MEDIA_*).
Works silently, instantly (<1ms), without requiring Spotify Premium or OAuth tokens.
"""

import ctypes
import time
from typing import Optional

VK_VOLUME_MUTE = 0xAD
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP = 0xAF
VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_MEDIA_STOP = 0xB2
VK_MEDIA_PLAY_PAUSE = 0xCD
KEYEVENTF_KEYUP = 0x0002

user32 = ctypes.windll.user32

def _send_key(vk_code: int):
    """Sends a single key down and key up event via Win32."""
    user32.keybd_event(vk_code, 0, 0, 0)
    time.sleep(0.02)
    user32.keybd_event(vk_code, 0, KEYEVENTF_KEYUP, 0)

def play_pause() -> str:
    """Toggles playback between play and pause."""
    _send_key(VK_MEDIA_PLAY_PAUSE)
    return "Playback toggled (play/pause)."

def next_track() -> str:
    """Skips to the next track."""
    _send_key(VK_MEDIA_NEXT_TRACK)
    return "Skipped to next track."

def previous_track() -> str:
    """Goes to the previous track."""
    _send_key(VK_MEDIA_PREV_TRACK)
    return "Skipped to previous track."

def stop() -> str:
    """Stops playback."""
    _send_key(VK_MEDIA_STOP)
    return "Playback stopped."

def volume_up(steps: int = 5) -> str:
    """Increases system volume."""
    for _ in range(steps):
        _send_key(VK_VOLUME_UP)
    return f"Volume raised ({steps} steps)."

def volume_down(steps: int = 5) -> str:
    """Decreases system volume."""
    for _ in range(steps):
        _send_key(VK_VOLUME_DOWN)
    return f"Volume lowered ({steps} steps)."

def toggle_mute() -> str:
    """Mutes or unmutes system sound."""
    _send_key(VK_VOLUME_MUTE)
    return "Audio mute toggled."

def play_song(song_query: str) -> str:
    """Searches and plays a song using the core tools engine."""
    from tools.core_tools import play_music
    return play_music(song_query)
