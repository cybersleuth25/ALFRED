import queue

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

def push_state(state_name: str):
    """Pushes a UI wave state change (idle, listening, processing, speaking)"""
    global current_state
    current_state = state_name
    event_queue.put({"type": "state", "value": state_name})

def push_log(message: str, author: str = "System"):
    """Pushes a transcript log to the UI (author: System, User, Alfred)"""
    event_queue.put({"type": "transcript", "value": message, "author": author})

def push_caption(message: str):
    """Pushes a string to the UI to be rendered as 3D particle text."""
    event_queue.put({"type": "caption", "value": message})

def push_globe(show: bool):
    """Shows or hides the globe intelligence view in the UI."""
    event_queue.put({"type": "globe", "value": show})

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
