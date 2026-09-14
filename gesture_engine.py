"""
Gesture Engine — Extensible Gesture Control Layer for Alfred
=============================================================
Decouples gesture detection from action execution via a registry pattern.
Supports 8 gestures with per-gesture cooldowns and SSE feedback.

Usage:
    import gesture_engine
    gesture_engine.init_default_gestures()
    gesture_engine.process_frame(landmarks)  # called from vision_engine
"""

import time
import threading

import shared

# ── Gesture Registry ──
# Maps gesture_name → { "detector": fn(landmarks) -> bool, "action": fn(), "cooldown_frames": int }
_registry = {}
_cooldowns = {}       # gesture_name → remaining cooldown frames
_registry_lock = threading.Lock()


def register(name: str, detector_fn, action_fn, cooldown_frames: int = 30):
    """
    Register a gesture with its detector and action callback.

    Args:
        name: Unique gesture name (e.g., "palm", "thumbs_up")
        detector_fn: Callable(landmarks) -> bool. Returns True if gesture detected.
        action_fn: Callable() -> None. Fired when gesture is detected and cooldown expired.
        cooldown_frames: Minimum frames between consecutive triggers of this gesture.
    """
    with _registry_lock:
        _registry[name] = {
            "detector": detector_fn,
            "action": action_fn,
            "cooldown_frames": cooldown_frames,
        }
        _cooldowns[name] = 0


def unregister(name: str):
    """Remove a gesture from the registry."""
    with _registry_lock:
        _registry.pop(name, None)
        _cooldowns.pop(name, None)


def list_gestures() -> list:
    """Returns list of registered gesture names."""
    with _registry_lock:
        return list(_registry.keys())


# ══════════════════════════════════════════════════════════
#  GESTURE DETECTORS
#  Each takes MediaPipe hand landmarks and returns bool
# ══════════════════════════════════════════════════════════

def _count_fingers_up(landmarks) -> int:
    """Count how many of the 4 fingers (index, middle, ring, pinky) are extended."""
    tips = [8, 12, 16, 20]
    mcps = [5, 9, 13, 17]
    count = 0
    for tip_idx, mcp_idx in zip(tips, mcps):
        if landmarks[tip_idx].y < landmarks[mcp_idx].y:
            count += 1
    return count


def _is_thumb_extended(landmarks) -> bool:
    """Check if thumb is extended (simplified: works for both hands)."""
    thumb_tip = landmarks[4]
    thumb_ip = landmarks[3]
    thumb_mcp = landmarks[2]
    # Check if thumb tip is further from palm center than the IP joint
    wrist = landmarks[0]
    # Use x-axis distance from wrist to determine extension
    dist_tip = abs(thumb_tip.x - wrist.x)
    dist_ip = abs(thumb_ip.x - wrist.x)
    return dist_tip > dist_ip


def _is_thumb_down(landmarks) -> bool:
    """Check if thumb is pointing downward."""
    thumb_tip = landmarks[4]
    thumb_mcp = landmarks[2]
    wrist = landmarks[0]
    # Thumb tip below MCP and below wrist
    return (thumb_tip.y > thumb_mcp.y and
            thumb_tip.y > wrist.y and
            _count_fingers_up(landmarks) == 0)


def _thumb_index_distance(landmarks) -> float:
    """Calculate distance between thumb tip and index fingertip."""
    thumb_tip = landmarks[4]
    index_tip = landmarks[8]
    return ((thumb_tip.x - index_tip.x)**2 + (thumb_tip.y - index_tip.y)**2) ** 0.5


# ── Individual Gesture Detectors ──

def detect_palm(landmarks) -> bool:
    """✋ Open palm — all 4 fingers up + thumb extended."""
    return _count_fingers_up(landmarks) >= 4 and _is_thumb_extended(landmarks)


def detect_fist(landmarks) -> bool:
    """✊ Closed fist — all fingers down, thumb not extended."""
    return _count_fingers_up(landmarks) == 0 and not _is_thumb_extended(landmarks)


def detect_ok(landmarks) -> bool:
    """👌 OK sign — thumb+index circle with 2+ other fingers up."""
    return _thumb_index_distance(landmarks) < 0.06 and _count_fingers_up(landmarks) >= 2


def detect_thumbs_up(landmarks) -> bool:
    """👍 Thumbs up — only thumb extended, all fingers closed, thumb tip above wrist."""
    thumb_tip = landmarks[4]
    wrist = landmarks[0]
    return (_is_thumb_extended(landmarks) and
            _count_fingers_up(landmarks) == 0 and
            thumb_tip.y < wrist.y)  # Thumb pointing UP


def detect_thumbs_down(landmarks) -> bool:
    """👎 Thumbs down — thumb pointing down, all fingers closed."""
    return _is_thumb_down(landmarks)


def detect_peace(landmarks) -> bool:
    """✌️ Peace / V-sign — index + middle up, ring + pinky down."""
    index_up = landmarks[8].y < landmarks[5].y
    middle_up = landmarks[12].y < landmarks[9].y
    ring_down = landmarks[16].y >= landmarks[13].y
    pinky_down = landmarks[20].y >= landmarks[17].y
    return index_up and middle_up and ring_down and pinky_down


def detect_point_up(landmarks) -> bool:
    """☝️ Point up — only index finger up, all others down."""
    index_up = landmarks[8].y < landmarks[5].y
    middle_down = landmarks[12].y >= landmarks[9].y
    ring_down = landmarks[16].y >= landmarks[13].y
    pinky_down = landmarks[20].y >= landmarks[17].y
    return index_up and middle_down and ring_down and pinky_down and not _is_thumb_extended(landmarks)


def detect_pinch(landmarks) -> bool:
    """Pinch — thumb tip very close to index tip, hand active."""
    wrist = landmarks[0]
    index_tip = landmarks[8]
    thumb_tip = landmarks[4]
    
    # Hand must have reasonable extension from wrist
    if abs(index_tip.y - wrist.y) < 0.08 or abs(thumb_tip.y - wrist.y) < 0.08:
        return False

    dist = _thumb_index_distance(landmarks)
    fingers = _count_fingers_up(landmarks)
    # Pinch = thumb+index touching, with 1 or fewer other fingers up
    return dist < 0.04 and fingers <= 1


# ══════════════════════════════════════════════════════════
#  GESTURE ACTIONS
#  Each is a no-arg callable fired when the gesture triggers
# ══════════════════════════════════════════════════════════

def action_palm():
    """Toggle pause/resume Alfred's speech."""
    try:
        import voice_engine
        paused = voice_engine.toggle_pause()
        action = "paused" if paused else "resumed"
        print(f"[Gesture Engine] [Palm] Speech {action}.")
        shared.push_state("speaking" if not paused else "idle")
    except Exception as e:
        print(f"[Gesture Engine] Palm action error: {e}")


def action_fist():
    """Stop speaking immediately."""
    try:
        import voice_engine
        if voice_engine.is_speaking():
            voice_engine.stop_speaking()
            print("[Gesture Engine] [Fist] Speech stopped.")
    except Exception as e:
        print(f"[Gesture Engine] Fist action error: {e}")


def action_ok():
    """Dismiss current alert / confirm action."""
    if shared.hidden_mode:
        shared.hidden_mode = False
        shared.threat_level = "none"
        shared.threat_score = 0.0
        print("[Gesture Engine] [OK] Alert dismissed.")
    else:
        print("[Gesture Engine] [OK] Acknowledged.")


def action_thumbs_up():
    """Positive acknowledgment — could confirm a pending action."""
    print("[Gesture Engine] [Thumbs Up] Acknowledged positively.")
    shared.push_log("User gave a thumbs up gesture.", "Gesture")


def action_thumbs_down():
    """Negative signal — could reject a pending suggestion."""
    print("[Gesture Engine] [Thumbs Down] Rejected / Negative.")
    shared.push_log("User gave a thumbs down gesture.", "Gesture")


def action_peace():
    """Take a screenshot."""
    try:
        from tools import system_tools
        result = system_tools.take_screenshot()
        print(f"[Gesture Engine] [Peace] Screenshot taken: {result}")
        shared.push_log(f"Screenshot taken via gesture: {result}", "Gesture")
    except Exception as e:
        print(f"[Gesture Engine] Peace action error: {e}")


def action_point_up():
    """Scroll up / volume up nudge."""
    try:
        from tools import system_tools
        # Small volume increase as a demo action
        print("[Gesture Engine] [Point Up] Volume nudge up.")
        system_tools.set_volume("up")
    except Exception as e:
        print(f"[Gesture Engine] Point Up action error: {e}")


def action_pinch():
    """Pinch — precision action placeholder (mute toggle)."""
    try:
        from tools import core_tools
        result = core_tools.toggle_system_volume("toggle")
        print(f"[Gesture Engine] [Pinch] Volume toggle: {result}")
    except Exception as e:
        print(f"[Gesture Engine] Pinch action error: {e}")


# ══════════════════════════════════════════════════════════
#  INITIALIZATION
# ══════════════════════════════════════════════════════════

def init_default_gestures():
    """Register all 8 built-in gestures with their detectors and actions."""
    register("palm",        detect_palm,        action_palm,        cooldown_frames=30)
    register("fist",        detect_fist,        action_fist,        cooldown_frames=30)
    register("ok",          detect_ok,          action_ok,          cooldown_frames=30)
    register("thumbs_up",   detect_thumbs_up,   action_thumbs_up,   cooldown_frames=45)
    register("thumbs_down", detect_thumbs_down, action_thumbs_down, cooldown_frames=45)
    register("peace",       detect_peace,       action_peace,       cooldown_frames=60)
    register("point_up",    detect_point_up,    action_point_up,    cooldown_frames=20)
    register("pinch",       detect_pinch,       action_pinch,       cooldown_frames=30)
    print("[Gesture Engine] 8 default gestures registered.")


# ══════════════════════════════════════════════════════════
#  MAIN PROCESSING — called from vision_engine every frame
# ══════════════════════════════════════════════════════════

def process_frame(landmarks) -> str:
    """
    Checks all registered gestures against the given hand landmarks.
    Fires the action of the first matching gesture whose cooldown has expired.

    Args:
        landmarks: MediaPipe hand landmarks list (21 landmarks).

    Returns:
        Name of the detected gesture, or "" if none.
    """
    if landmarks is None:
        return ""

    with _registry_lock:
        # Tick down all cooldowns
        for name in _cooldowns:
            _cooldowns[name] = max(0, _cooldowns[name] - 1)

        # Check gestures in priority order (registry insertion order)
        for name, entry in _registry.items():
            # Skip if still in cooldown
            if _cooldowns.get(name, 0) > 0:
                continue

            try:
                detected = entry["detector"](landmarks)
            except Exception:
                continue

            if detected:
                # Fire the action
                try:
                    entry["action"]()
                except Exception as e:
                    print(f"[Gesture Engine] Action '{name}' error: {e}")

                # Set cooldown
                _cooldowns[name] = entry["cooldown_frames"]

                # Push to frontend
                shared.push_gesture(name)

                return name

    return ""
