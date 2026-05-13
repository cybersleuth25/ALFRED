import queue
import os
import ollama
from dotenv import load_dotenv

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

# Protocol Omega State (consumed by frontend via API/SSE)
omega_active = False
omega_session_id = None
omega_pomodoro_cycle = 0
omega_phase = "idle"            # "focus", "short_break", "long_break", "idle"
omega_phase_remaining = 0       # seconds remaining in current phase
omega_distractions = 0
omega_session_start = 0         # timestamp
omega_daily_goal_minutes = 240  # default: 4 hours
omega_daily_progress = 0        # minutes studied today
omega_streak = 0                # consecutive study days

# --- LLM & Brain Configuration ---
LLM_HOST = os.getenv("LLM_HOST", "http://localhost:11434")
REMOTE_LLM_HOST = os.getenv("REMOTE_LLM_HOST", "http://localhost:11434")
REMOTE_LLM_MODEL = os.getenv("REMOTE_LLM_MODEL", "llama3:70b")
LOCAL_MODEL = "qwen3:4b"
USE_REMOTE_BRAIN = os.getenv("USE_REMOTE_BRAIN", "false").lower() == "true"

# Clients
local_client = ollama.Client(host=LLM_HOST)
remote_client = None
if USE_REMOTE_BRAIN:
    try:
        remote_client = ollama.Client(host=REMOTE_LLM_HOST)
    except Exception:
        pass

def get_brain():
    """Returns the active client and model name based on settings and health."""
    if USE_REMOTE_BRAIN and remote_client:
        try:
            # remote_client.list() is a lightweight check
            return remote_client, REMOTE_LLM_MODEL
        except Exception:
            return local_client, LOCAL_MODEL
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

def push_notification(message: str):
    """
    Sends a push notification to the user's phone via Telegram.
    This is a convenience wrapper — any module can call shared.push_notification()
    without needing to import telegram_notifier directly.
    Silently fails if Telegram is not configured.
    """
    try:
        import telegram_notifier
        if telegram_notifier.is_available():
            telegram_notifier.send_alert(message)
    except ImportError:
        pass
    except Exception:
        pass
