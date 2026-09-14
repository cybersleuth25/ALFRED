"""
Mood Engine — Emotional Intelligence for Alfred
=================================================
Tracks the user's emotional state in real-time via camera frames (UniFace/MediaPipe),
logs historical mood trends in SQLite, and provides adaptive persona instructions
so Alfred dynamically shifts his tone (e.g. gentle/supportive when tired or stressed,
energetic/witty when happy, crisp when focused).
"""

import time
import os
import shared
import memory_engine
from datetime import datetime

# Emotion -> Tone Adaptation Instructions for Alfred's LLM
EMOTION_TONE_MAP = {
    "happy": (
        "USER MOOD: HAPPY / ENERGETIC. "
        "Tone adjustment: Be witty, cheerful, and share in their positive energy. Keep your charming British wit sharp."
    ),
    "sad": (
        "USER MOOD: SUBDUED / SAD. "
        "Tone adjustment: Adopt a gentle, compassionate, and supportive tone. Be concise, do not overload them, and offer sincere assistance."
    ),
    "angry": (
        "USER MOOD: FRUSTRATED / STRESSED. "
        "Tone adjustment: Be exceptionally calm, highly efficient, and direct. Avoid unnecessary chatter; execute instructions swiftly and cleanly."
    ),
    "tired": (
        "USER MOOD: TIRED / FATIGUED. "
        "Tone adjustment: Speak with soft brevity and calm warmth. Gently remind them to rest or hydrate if appropriate."
    ),
    "surprised": (
        "USER MOOD: SURPRISED / CURIOUS. "
        "Tone adjustment: Be engaging, clear, and provide context quickly to satisfy their curiosity."
    ),
    "neutral": (
        "USER MOOD: NEUTRAL / FOCUSED. "
        "Tone adjustment: Standard polished butler persona. Crisp, helpful, and professional."
    ),
}

_last_log_time = 0
LOG_INTERVAL = 30  # Minimum seconds between SQLite mood snapshots


def log_mood_snapshot(emotion: str, confidence: float = 1.0, context: str = None) -> bool:
    """Logs the user's detected emotion into SQLite and updates shared state."""
    global _last_log_time
    clean_emotion = emotion.lower().strip()
    if not clean_emotion:
        return False

    shared.dominant_emotion = clean_emotion
    shared.current_ai_mood = clean_emotion

    now = time.time()
    if now - _last_log_time >= LOG_INTERVAL:
        act = context or getattr(shared, 'context_current_activity', 'idle')
        try:
            memory_engine.log_user_mood(
                emotion=clean_emotion,
                confidence=float(confidence),
                context=act
            )
            _last_log_time = now
            return True
        except Exception as e:
            print(f"[Mood Engine] Failed to log mood snapshot: {e}")
            return False
    return False


def get_current_mood() -> dict:
    """Returns the current live emotion and recent dominant trend."""
    live = getattr(shared, 'dominant_emotion', 'neutral')
    recent_dominant = memory_engine.get_dominant_mood_recent(minutes=30)
    return {
        "live_emotion": live,
        "dominant_emotion_30m": recent_dominant,
        "timestamp": datetime.now().isoformat()
    }


def get_mood_prompt_modifier() -> str:
    """
    Returns dynamic system prompt instructions adapting Alfred's tone
    based on current and recent user emotion.
    """
    live = getattr(shared, 'dominant_emotion', None)
    recent = memory_engine.get_dominant_mood_recent(minutes=30)

    target_emotion = live if live and live != "neutral" else recent
    return EMOTION_TONE_MAP.get(target_emotion, EMOTION_TONE_MAP["neutral"])


def get_mood_timeline(hours: int = 24) -> list:
    """Returns historical mood snapshots for frontend visualization."""
    return memory_engine.get_recent_moods(hours=hours)
