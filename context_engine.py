"""
Context Engine — Alfred's Sixth Sense
========================================
A background daemon that passively builds real-time contextual awareness:

1. Activity Classifier: Reads active window title + ScreenPipe OCR → categorizes
   what the user is doing (coding, studying, browsing, entertainment, etc.)

2. Presence Detector: Borrows camera frames from security_engine → detects if
   the user is present, away, or idle at the desk.

3. Dwell Timer: Tracks how long the user has been on the same activity or staring
   at the same screen content.

4. Proactive Interventions: When conditions are met (stuck on error, long session,
   user returns), Alfred speaks proactively without being asked.

All processing is local. No data leaves the machine.
"""

import threading
import time
import os
import random
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

import shared
import memory_engine

# Import push notification module (optional)
try:
    import telegram_notifier
    _telegram_available = telegram_notifier.is_available()
except ImportError:
    _telegram_available = False

# ── Configuration (from .env) ──
ENABLED = os.getenv("CONTEXT_ENGINE_ENABLED", "true").lower() == "true"
SCAN_INTERVAL = int(os.getenv("CONTEXT_SCAN_INTERVAL", "30"))
SNAPSHOT_INTERVAL = int(os.getenv("CONTEXT_SNAPSHOT_INTERVAL", "60"))
INTERVENTION_COOLDOWN = int(os.getenv("CONTEXT_INTERVENTION_COOLDOWN", "300"))
STUCK_THRESHOLD = int(os.getenv("CONTEXT_STUCK_THRESHOLD", "600"))
BREAK_THRESHOLD = int(os.getenv("CONTEXT_BREAK_THRESHOLD", "5400"))
AWAY_THRESHOLD = int(os.getenv("CONTEXT_AWAY_THRESHOLD", "120"))
RETURN_GREETING_THRESHOLD = 300  # 5 minutes away before welcome-back message

USER_NAME = os.getenv("ALFRED_USER_NAME", "User")

# ── Activity Classification Rules ──
# These mirror study_mentor.py's whitelist/blacklist pattern but categorize instead of block

_ACTIVITY_RULES = {
    "coding": [
        'vs code', 'visual studio', 'code -', 'pycharm', 'intellij', 'eclipse',
        'android studio', 'jupyter', 'terminal', 'powershell', 'cmd', 'putty',
        'github', 'git', 'stack overflow', 'stackoverflow', 'docker',
        'postman', 'wireshark', 'virtualbox', 'vmware',
        'xampp', 'wamp', 'mysql', 'pgadmin', 'mongodb', 'redis',
        'antigravity', 'buggyverse',
    ],
    "studying": [
        'notion', 'obsidian', 'google docs', 'google sheets',
        'word', 'excel', 'powerpoint', 'onenote',
        'pdf', 'acrobat', 'adobe scan',
        'zotero', 'mendeley', 'anki',
        'chatgpt', 'gemini', 'claude', 'ollama', 'lm studio',
        'khan academy', 'coursera', 'udemy', 'edx',
    ],
    "communication": [
        'discord', 'slack', 'teams', 'zoom', 'meet',
        'whatsapp', 'telegram', 'signal',
        'gmail', 'outlook', 'mail', 'thunderbird',
    ],
    "entertainment": [
        'netflix', 'prime video', 'hotstar', 'disney+',
        'instagram', 'tiktok', 'snapchat',
        'reddit', 'twitter', 'x.com', 'x - ',
        'facebook', 'shorts', 'reels',
        'crunchyroll', 'funimation',
        'steam', 'epic games', 'riot client', 'valorant', 'minecraft',
    ],
    "browsing": [
        'chrome', 'edge', 'firefox', 'brave', 'opera', 'safari',
    ],
    "media": [
        'spotify', 'youtube music', 'vlc', 'media player',
        'youtube',  # YouTube can be studying OR entertainment — defaults to media
    ],
}

# ── Proactive Intervention Lines ──

STUCK_LINES = [
    f"Sir, you have been on this for quite some time. Shall I search for the error or help you debug?",
    f"Master {USER_NAME}, I have noticed you have been staring at the same content for a while. Can I assist?",
    f"Pardon the observation, sir, but you appear to be stuck. Would you like me to research the issue?",
    f"You have been on this screen for over 10 minutes, sir. Sometimes a fresh perspective helps. Shall I look into it?",
]

BREAK_LINES = [
    f"Master {USER_NAME}, you have been working continuously for over 90 minutes. I strongly recommend a short break.",
    f"Sir, your dedication is admirable, but your brain needs rest. Please take a 5-minute break.",
    f"Pardon the interruption, Master {USER_NAME}, but you have been at it for quite a while. A break would do you good.",
    f"I suggest stepping away from the screen for a few minutes, sir. Sustained focus requires periodic rest.",
]

AWAY_PAUSE_LINES = [
    f"You appear to have stepped away, sir. I have paused your study timer.",
    f"I notice you have left your desk, Master {USER_NAME}. Timer paused until you return.",
]

RETURN_LINES = [
    "Welcome back, sir. You were working on {activity} for {duration} minutes before stepping away.",
    "Good to see you back, Master {USER_NAME}. You were {activity} before you left. Shall we continue?",
    "You have returned, sir. You stepped away for {away_minutes} minutes. Your previous activity was {activity}.",
]

# ── Thread Control ──
_running = False
_thread = None
_last_snapshot_time = 0
_last_intervention_time = 0
_last_screen_hash = None
_screen_hash_unchanged_since = 0
_activity_start_time = 0
_last_activity = "idle"
_user_was_away = False
_away_start_time = 0
_away_pause_spoken = False


def _safe_speak(message: str) -> bool:
    """Delegates to shared.safe_speak() — centralized TTS with state management."""
    try:
        return shared.safe_speak(message, author="Alfred")
    except Exception as e:
        print(f"[Context Engine] TTS failed: {e}")
        return False


def _can_intervene() -> bool:
    """Checks if enough time has passed since the last proactive intervention."""
    global _last_intervention_time
    now = time.time()
    if now - _last_intervention_time < INTERVENTION_COOLDOWN:
        return False
    return True


def _mark_intervened():
    """Records that an intervention just happened."""
    global _last_intervention_time
    _last_intervention_time = time.time()


def classify_activity(window_title: str) -> str:
    """
    Classifies the current activity based on the active window title.
    Returns one of: coding, studying, communication, entertainment, browsing, media, idle, unknown
    """
    if not window_title or window_title.strip() == "":
        return "idle"

    lower = window_title.lower()

    # Check each category (more specific categories first)
    for category in ["coding", "studying", "communication", "entertainment", "media", "browsing"]:
        keywords = _ACTIVITY_RULES.get(category, [])
        for keyword in keywords:
            if keyword in lower:
                return category

    return "unknown"


def _get_active_window_title() -> str:
    """Gets the currently active window title using pygetwindow."""
    try:
        import pygetwindow as gw
        active = gw.getActiveWindow()
        if active and active.title:
            return active.title
    except Exception:
        pass
    return ""


def _detect_presence() -> str:
    """
    Detects user presence using the security engine's camera feed.
    Returns: 'present', 'away', or 'unknown'
    """
    try:
        import security_engine
        if not security_engine.is_running():
            return "unknown"

        frame = security_engine.get_latest_frame()
        if frame is None:
            return "unknown"

        # Use the face_present flag that security_engine already maintains
        if shared.face_present:
            return "present"
        else:
            return "away"
    except Exception:
        return "unknown"


def _get_screen_hash() -> str:
    """Gets the current screen's perceptual hash for change detection."""
    try:
        from PIL import ImageGrab
        import imagehash
        screenshot = ImageGrab.grab()
        # Downscale for faster hashing
        screenshot = screenshot.resize((160, 90))
        return str(imagehash.average_hash(screenshot))
    except Exception:
        return None


def get_context_summary() -> str:
    """
    Returns a human-readable summary of the user's recent activity.
    Called by alfred.py for context-aware greetings.
    """
    activity = shared.context_current_activity
    if activity == "idle" or activity == "unknown":
        return ""

    duration_sec = time.time() - shared.context_activity_since
    duration_min = int(duration_sec / 60)

    if duration_min < 2:
        return ""

    activity_descriptions = {
        "coding": "coding",
        "studying": "studying",
        "browsing": "browsing the web",
        "entertainment": "watching entertainment",
        "communication": "in a conversation",
        "media": "listening to media",
    }

    desc = activity_descriptions.get(activity, activity)
    return f"You have been {desc} for about {duration_min} minutes."


def get_current_context() -> dict:
    """Returns the current context state as a dictionary (for API endpoints)."""
    now = time.time()
    return {
        "activity": shared.context_current_activity,
        "activity_since": shared.context_activity_since,
        "activity_duration_seconds": int(now - shared.context_activity_since) if shared.context_activity_since > 0 else 0,
        "presence": shared.context_presence,
        "away_since": shared.context_away_since,
        "dwell_seconds": shared.context_dwell_seconds,
        "active_window": _get_active_window_title(),
    }


def get_activity_timeline(minutes: int = 60) -> list:
    """Returns the activity timeline from the database for the last N minutes."""
    return memory_engine.get_recent_context(minutes)


# ============================
#  MAIN DAEMON LOOP
# ============================

def _context_loop():
    """The main background loop that continuously monitors context."""
    global _running, _last_snapshot_time, _last_screen_hash
    global _screen_hash_unchanged_since, _activity_start_time
    global _last_activity, _user_was_away, _away_start_time, _away_pause_spoken

    print("[Context Engine] Daemon started.")

    # Initialize timers
    _activity_start_time = time.time()
    _screen_hash_unchanged_since = time.time()
    _last_snapshot_time = time.time()
    shared.context_activity_since = time.time()

    while _running:
        try:
            now = time.time()

            # ── 1. Activity Classification ──
            window_title = _get_active_window_title()
            activity = classify_activity(window_title)

            # Update shared state
            if activity != _last_activity:
                _last_activity = activity
                _activity_start_time = now
                shared.context_activity_since = now
                shared.context_current_activity = activity
                shared.push_context_state()

            # Calculate dwell time (how long on current activity)
            activity_dwell = int(now - _activity_start_time)
            shared.context_dwell_seconds = activity_dwell

            # ── 2. Screen Hash (Change Detection) ──
            current_hash = _get_screen_hash()
            if current_hash:
                if current_hash == _last_screen_hash:
                    # Screen hasn't changed
                    screen_stale_seconds = int(now - _screen_hash_unchanged_since)
                else:
                    # Screen changed — reset
                    _last_screen_hash = current_hash
                    _screen_hash_unchanged_since = now
                    screen_stale_seconds = 0
            else:
                screen_stale_seconds = 0

            # ── 3. Presence Detection ──
            presence = _detect_presence()
            old_presence = shared.context_presence

            if presence != "unknown":
                shared.context_presence = presence

                # User just went away
                if presence == "away" and old_presence == "present":
                    _user_was_away = True
                    _away_start_time = now
                    shared.context_away_since = now
                    _away_pause_spoken = False

                # User is still away — check thresholds
                if presence == "away" and _user_was_away:
                    away_duration = now - _away_start_time

                    # Pause study timer if in Focus Mode and away for >AWAY_THRESHOLD
                    if away_duration > AWAY_THRESHOLD and not _away_pause_spoken:
                        if shared.omega_active and shared.omega_phase == "focus":
                            if _can_intervene():
                                _safe_speak(random.choice(AWAY_PAUSE_LINES))
                                _mark_intervened()
                                _away_pause_spoken = True

                # User just came back
                if presence == "present" and _user_was_away:
                    away_duration = now - _away_start_time
                    _user_was_away = False
                    shared.context_away_since = 0

                    # Welcome back if they were away for >5 minutes
                    if away_duration > RETURN_GREETING_THRESHOLD:
                        if _can_intervene():
                            away_min = int(away_duration / 60)
                            activity_desc = _last_activity if _last_activity != "idle" else "your previous task"
                            duration_min = int((_away_start_time - _activity_start_time) / 60) if _activity_start_time > 0 else 0
                            msg = random.choice(RETURN_LINES).format(
                                activity=activity_desc,
                                duration=duration_min,
                                away_minutes=away_min,
                                USER_NAME=USER_NAME
                            )
                            _safe_speak(msg)
                            _mark_intervened()

            # ── 4. Proactive Interventions ──

            # 4a. Stuck Detection: Same screen for >STUCK_THRESHOLD while coding
            if (activity == "coding" and screen_stale_seconds > STUCK_THRESHOLD
                    and _can_intervene()):
                _safe_speak(random.choice(STUCK_LINES))
                _mark_intervened()
                # Reset the hash timer so we don't re-trigger immediately
                _screen_hash_unchanged_since = now

            # 4b. Break Suggestion: Same activity for >BREAK_THRESHOLD
            if (activity_dwell > BREAK_THRESHOLD
                    and activity in ("coding", "studying", "browsing")
                    and _can_intervene()):
                _safe_speak(random.choice(BREAK_LINES))
                _mark_intervened()

            # ── 5. Periodic DB Snapshot ──
            if now - _last_snapshot_time >= SNAPSHOT_INTERVAL:
                try:
                    memory_engine.store_context_snapshot(
                        activity=activity,
                        active_window=window_title[:200] if window_title else "",
                        screen_hash=current_hash or "",
                        presence=presence,
                        dwell_seconds=activity_dwell
                    )
                    _last_snapshot_time = now
                except Exception as e:
                    print(f"[Context Engine] Snapshot storage failed: {e}")

            # ── 6. Push state to frontend ──
            shared.push_context_state()

        except Exception as e:
            print(f"[Context Engine] Loop error: {e}")

        time.sleep(SCAN_INTERVAL)

    print("[Context Engine] Daemon stopped.")


# ============================
#  PUBLIC API
# ============================

def start_context_daemon():
    """Starts the Context Engine background thread."""
    global _running, _thread
    if not ENABLED:
        print("[Context Engine] Disabled via CONTEXT_ENGINE_ENABLED=false.")
        return
    if _running:
        return

    _running = True
    _thread = threading.Thread(target=_context_loop, daemon=True, name="ContextEngine")
    _thread.start()
    print("[System] Context Awareness Engine started.")


def stop_context_daemon():
    """Stops the Context Engine background thread."""
    global _running
    _running = False
    if _thread and _thread.is_alive():
        _thread.join(timeout=5)
    print("[System] Context Awareness Engine stopped.")


def is_active() -> bool:
    """Returns True if the context engine daemon is running."""
    return _running
