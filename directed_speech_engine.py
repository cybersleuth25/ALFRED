"""
Directed Speech Recognition Engine for Alfred / JARVIS.
======================================================
Intelligently determines whether an incoming spoken utterance is directed at the AI
assistant or is side-talk (conversing with someone else in the room, on a phone call,
or muttering to themselves).

Key Signals Evaluated:
1. Lexical Invocations: Assistant names, vocatives, wake words ('alfred', 'jarvis', 'friday', 'suno alfred', etc.)
2. Imperatives & Queries: Commands directed to software ('play', 'open', 'what is', 'weather', 'chalao', 'batao', etc.)
3. Interpersonal Side-Talk Vocatives: Words addressed to other humans ('bro', 'bhai', 'yaar', 'mom', 'dad', 'guys', etc.)
4. Telephony & Interpersonal Dialogue Patterns: 'on a call', 'call you later', 'phone uthao', 'pass the', 'did she say', etc.)
5. Turn-Taking Context: Active confirmation prompts, awaiting user choice, or recent assistant turn.
6. Multi-Modal Vision Gaze: Head pose alignment check from security engine camera feed.
7. Safe Ignored Policy: Drops side chatter silently with zero annoying nudges.
"""

import re
import os
import time
import shared

# ── Explicit Assistant Vocatives & Wake Identifiers ──
ASSISTANT_IDENTIFIERS = frozenset([
    'alfred', 'jarvis', 'friday', 'alford', 'elfred', 'alfie', 'tarvis',
    'suno alfred', 'suno jarvis', 'suno friday', 'hey alfred', 'hey jarvis',
    'hey friday', 'yo alfred', 'assistant', 'computer', 'aal-fred', 'jarwis'
])

# ── Interpersonal Vocatives (Strong Indicator of talking to another human) ──
SIDE_TALK_VOCATIVES = [
    r'\b(bro|dude|bhai|yaar|bhaiya|didi|mom|dad|mummy|papa|uncle|auntie|guys|man|babe|baby|brotha|amma|appa|sirji)\b',
    r'\b(listen bro|sun bhai|bhai sun|yaar sun|arey yaar|arre bhai)\b',
]

# ── Third-Party Dialogue & Telephony Patterns ──
SIDE_TALK_PATTERNS = [
    # Phone calls
    r'\b(call you (later|back)|on a call|phone (pe|par)|phone uthao|disconnect kar|voice nahi aa rahi|can you hear me)\b',
    r'\b(hello haan|haan bolo|haan bhai|accha theek hai rakho|phone rakho)\b',
    # Talking to someone in the room
    r'\b(did (you|he|she|they) (see|hear|tell|say|go|come|eat))\b',
    r'\b(she told|he told|they said|she said|he said|usne bola|unhone bola)\b',
    r'\b(pass (me )?(the|that)|give (me )?(the|that)|mere ko de|mujhe do|paani do|bottle do)\b',
    r'\b(kahan (hai|gaya|ja raha)|kya kar raha hai|kab aayega|chalo chalein|let\'s go guys)\b',
    r'\b(khana (kha liya|ready hai|laao)|gate (band|kholo)|door (open|close)|light band kar)\b',
    # Self-talk / programmer muttering
    r'\b(wait why is this|let me see|let\'s see|syntax error|undefined is not|null pointer|where was i)\b',
    r'\b(why did this happen|compiler error|stack trace|line \d+)\b',
]

# ── Direct Assistant Command Imperatives & Queries ──
ASSISTANT_COMMAND_PATTERNS = [
    # Queries & Requests
    r'^(what|who|where|when|why|how|which|tell me|explain|describe|calculate|summarize)\b',
    r'^(can you|could you|would you|please|i want to|help me)\b',
    # System & Media Imperatives
    r'^(play|open|launch|start|stop|pause|resume|skip|remind|set|search|show|switch|lock|mute|unmute)\b',
    # Hindi / Hinglish Action Verbs
    r'\b(chalao|bajao|sunao|karo|batao|dikhao|lagao|rok do|band karo|shuru karo|badlo)\b',
    r'^(kaise ho|namaste|kya haal|shukriya|dhanyawad|so jao|aaram karo|chup ho jao)\b',
    r'\b(mera gaana|mere gaane|daily gaane|spotify|weather|briefing|routine)\b',
]

# Follow-up conversational window in seconds (after Alfred finishes answering)
ATTENTIVE_WINDOW_SECONDS = float(os.getenv("ATTENTIVE_FOLLOWUP_TIMEOUT", "8.0"))

def is_speech_directed(text: str, context: dict = None) -> tuple[bool, str, float]:
    """
    Evaluates whether an utterance is directed at Alfred/JARVIS or is side-talk.
    
    Returns:
        (is_directed: bool, reason: str, confidence: float)
    """
    if not text or not text.strip():
        return False, "empty_speech", 0.0

    lower = text.lower().strip()
    words = lower.split()
    
    # ── SIGNAL 0: Acoustic Self-Echo Rejection ──
    # If the utterance matches what Alfred recently spoke through speakers, reject immediately!
    try:
        import voice_engine
        if voice_engine.is_self_echo(text):
            return False, "self_echo_from_speakers", 1.0
    except Exception:
        pass

    # ── SIGNAL 1: Explicit Assistant Name / Wake Invocation ──
    for name in ASSISTANT_IDENTIFIERS:
        if name in lower:
            return True, "explicit_assistant_name", 1.0

    # ── SIGNAL 2: Active Dialogue State Context ──
    # If Alfred explicitly asked the user for confirmation or choice,
    # immediate replies like "yes", "sure", "no", "cancel", "friday" are 100% directed.
    if getattr(shared, 'awaiting_study_confirmation', False):
        if any(w in lower for w in ['yes', 'yeah', 'sure', 'do it', 'confirm', 'start', 'no', 'nope', 'cancel', 'haan', 'nahi']):
            return True, "dialogue_confirmation_answer", 0.98

    # ── Pre-compute side-talk regex matches (used by multiple signals below) ──
    has_side_voc = any(bool(re.search(pat, lower)) for pat in SIDE_TALK_VOCATIVES)
    has_side_pat = any(bool(re.search(pat, lower)) for pat in SIDE_TALK_PATTERNS)

    # ── SIGNAL 2b: Active Conversation Mode ──
    # If Alfred is currently awake and awaiting user command in an active conversational turn,
    # and no human-addressed vocative or phone pattern is present, treat as directed!
    if getattr(shared, 'alfred_awake', False):
        if not has_side_voc and not has_side_pat:
            return True, "active_conversation_mode", 0.90

    # ── SIGNAL 3: Interpersonal Vocative Check (Talking to another human) ──
    if has_side_voc:
        # Check if the assistant's name was also used (e.g. "Bro alfred, play music")
        has_assistant_name = any(name in lower for name in ASSISTANT_IDENTIFIERS)
        if not has_assistant_name:
            return False, "interpersonal_vocative_detected", 0.95

    # ── SIGNAL 4: Telephony / Third-Party Conversational Pattern ──
    if has_side_pat:
        return False, "side_conversation_pattern_detected", 0.92

    # ── SIGNAL 5: Assistant Command / Query Imperatives ──
    for pat in ASSISTANT_COMMAND_PATTERNS:
        if re.search(pat, lower):
            return True, "assistant_command_imperative", 0.88

    # ── SIGNAL 6: Multi-Modal Head Pose & Visual Gaze Check ──
    try:
        user_facing = getattr(shared, 'user_facing_camera', True)
        if not user_facing:
            # User's head is turned sideways (>35 degrees) talking away from screen
            # Unless they used a direct imperative or wake word, treat as side-talk
            return False, "head_turned_away_from_screen", 0.85
    except Exception:
        pass

    # ── SIGNAL 7: Attentive Follow-up Window ──
    # If Alfred recently finished speaking (within ATTENTIVE_WINDOW_SECONDS),
    # short contextual utterances ("thank you", "next", "great", "ok", "got it")
    # are recognized as natural dialogue turn continuations.
    now = time.time()
    last_spoken = getattr(shared, 'last_assistant_speech_time', 0.0)
    time_since_speech = now - last_spoken

    if 0 < time_since_speech <= ATTENTIVE_WINDOW_SECONDS:
        if len(words) <= 5 and not has_side_vocative and not has_side_pattern:
            return True, f"attentive_turn_followup ({time_since_speech:.1f}s)", 0.75

    # ── SIGNAL 8: Fast Brain Verification for Ambiguous Sentences ──
    # If the sentence is longer than 4 words and ambiguous, check fast brain if enabled
    if len(words) >= 4 and os.getenv("ENABLE_BRAIN_DIRECTED_VERIFIER", "false").lower() == "true":
        try:
            directed_by_llm = _fast_brain_directed_check(text)
            if directed_by_llm is not None:
                return directed_by_llm, "fast_brain_classification", 0.85
        except Exception:
            pass

    # Default fail-safe: If not clearly directed, assume side-talk to prevent unwanted interruptions
    return False, "unrecognized_direction_safe_ignore", 0.65


def _fast_brain_directed_check(text: str) -> bool | None:
    """Uses the fast local/Groq model to classify ambiguous utterances (<200ms)."""
    client, model_name = shared.get_brain(smart=False)
    if not client:
        return None
    try:
        prompt = (
            f"Determine if this spoken sentence is DIRECTED TO an AI desktop assistant (asking for info, help, music, or command) "
            f"or SIDE_TALK (talking to another human, phone call, or self-muttering).\n"
            f"Utterance: \"{text}\"\n"
            f"Answer with ONLY ONE WORD: 'DIRECTED' or 'SIDE_TALK'."
        )
        res = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=5,
            timeout=2.0
        )
        ans = res.choices[0].message.content.strip().upper()
        return "DIRECTED" in ans
    except Exception:
        return None
