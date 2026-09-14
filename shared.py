import queue
import os
from dotenv import load_dotenv
import groq

load_dotenv()

# Global Event Queue for Server-Sent Events (SSE)
# Messages map to: {"type": "state", "value": "listening"} or {"type": "transcript", "value": "text", "author": "System"}
event_queue = queue.Queue()

# Global State Variables
focus_mode_active = False
current_state = "idle"
face_present = False
force_wake = False
alfred_awake = False
awaiting_study_confirmation = False
current_ai_mood = "calm"
speech_paused = False
gesture_detected = ""

# Protocol Omega State (consumed by frontend via API/SSE)
omega_active = False
omega_lockdown = False
omega_session_id = None
omega_pomodoro_cycle = 0
omega_phase = "idle"            # "focus", "short_break", "long_break", "idle"
omega_phase_remaining = 0       # seconds remaining in current phase
omega_distractions = 0
omega_session_start = 0         # timestamp
omega_daily_goal_minutes = 240  # default: 4 hours
omega_daily_progress = 0        # minutes studied today
omega_streak = 0                # consecutive study days
unseen_incidents = []           # security incidents unviewed in UI

# --- LLM & Brain Configuration ---
REMOTE_LLM_MODEL = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
LOCAL_MODEL = os.getenv("LLM_FAST_MODEL", "llama-3.1-8b-instant")
USE_REMOTE_BRAIN = True # Force true since we are using Groq

# Clients
local_client = None
remote_client = None
try:
    if os.getenv("GROQ_API_KEY"):
        remote_client = groq.Groq(api_key=os.getenv("GROQ_API_KEY"))
        local_client = remote_client
except Exception as e:
    print(f"[System] Failed to initialize Groq client: {e}")

def get_brain():
    """Returns the active client and model name based on settings and health."""
    # Always return Groq and the fast model by default for internal brain usage
    # (The main loop specifically requests REMOTE_LLM_MODEL when generating responses)
    return local_client, LOCAL_MODEL

def push_state(state_name: str):
    """Pushes a UI wave state change (idle, listening, processing, speaking)"""
    global current_state
    current_state = state_name
    event_queue.put({"type": "state", "value": state_name})

def push_mood(mood: str):
    """Pushes an AI emotional mood to the frontend Orb."""
    global current_ai_mood
    current_ai_mood = mood
    event_queue.put({"type": "mood", "value": mood})

def push_log(message: str, author: str = "System"):
    """Pushes a transcript log to the UI (author: System, User, Alfred)"""
    event_queue.put({"type": "transcript", "value": message, "author": author})

def push_caption(message: str):
    """Pushes a string to the UI to be rendered as 3D particle text."""
    event_queue.put({"type": "caption", "value": message})

def push_pause_state(paused: bool):
    """Pushes speech pause/resume state to the frontend."""
    global speech_paused
    speech_paused = paused
    event_queue.put({"type": "pause", "value": paused})

def push_gesture(gesture_name: str):
    """Pushes a detected gesture event to the frontend for visual feedback."""
    global gesture_detected
    gesture_detected = gesture_name
    event_queue.put({"type": "gesture", "value": gesture_name})

def push_globe(show: bool):
    """Shows or hides the globe intelligence view in the UI."""
    event_queue.put({"type": "globe", "value": show})

def push_mirror_mode(show: bool):
    """Toggles Smart Mirror UI mode."""
    event_queue.put({"type": "mirror", "value": show})

def push_omega_state():
    """Pushes the current Protocol Omega state to the frontend via SSE."""
    event_queue.put({"type": "omega", "value": {
        "active": omega_active,
        "phase": omega_phase,
        "remaining": omega_phase_remaining,
        "cycle": omega_pomodoro_cycle,
        "distractions": omega_distractions,
        "session_id": omega_session_id,
        "session_start": omega_session_start,
        "daily_goal": omega_daily_goal_minutes,
        "daily_progress": omega_daily_progress,
        "streak": omega_streak,
    }})

def push_persona_change(name: str, color: str, display_name: str):
    """Pushes a persona change to the UI."""
    event_queue.put({"type": "persona", "value": {
        "name": name,
        "color": color,
        "display_name": display_name
    }})

# ── Contextual Awareness State ──
context_current_activity = "idle"       # 'coding', 'studying', 'browsing', 'entertainment', etc.
context_activity_since = 0              # timestamp when current activity started
context_presence = "unknown"            # 'present', 'away', 'idle'
context_away_since = 0                  # timestamp when user left the desk
context_dwell_seconds = 0              # how long on same activity/content
context_last_intervention = 0          # timestamp of last proactive intervention

def push_context_state():
    """Pushes the current contextual awareness state to the frontend via SSE."""
    event_queue.put({"type": "context", "value": {
        "activity": context_current_activity,
        "activity_since": context_activity_since,
        "presence": context_presence,
        "away_since": context_away_since,
        "dwell_seconds": context_dwell_seconds,
    }})

def safe_speak(message: str, author: str = "Alfred") -> bool:
    """
    Centralized, thread-safe speech function used by background daemons
    (cron_engine, study_mentor, context_engine, etc.).
    Pushes state to UI, speaks via voice_engine, and restores previous state.
    """
    if not message or not message.strip():
        return False
    try:
        import voice_engine
        prev_state = current_state
        push_state("speaking")
        push_log(message, author)
        push_caption(message)
        voice_engine.speak(message)
        push_caption("")
        push_state("listening" if alfred_awake else "idle")
        return True
    except Exception as e:
        print(f"[shared.safe_speak] Error speaking: {e}")
        try:
            push_caption("")
            push_state("listening" if alfred_awake else "idle")
        except Exception:
            pass
        return False

def push_notification(message: str, author: str = None):
    """
    Sends a push notification to the user's phone via Telegram.
    This is a convenience wrapper — any module can call shared.push_notification()
    without needing to import telegram_notifier directly.
    Silently fails if Telegram is not configured.
    """
    try:
        import telegram_notifier
        if telegram_notifier.is_available():
            prefix = f"[{author}] " if author else ""
            telegram_notifier.send_alert(f"{prefix}{message}")
    except ImportError:
        pass
    except Exception:
        pass
