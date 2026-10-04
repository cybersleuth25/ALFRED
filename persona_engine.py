"""
Persona Engine for Alfred.
============================
Supports hot-swappable AI personalities with different voice profiles,
system prompt styles, and UI accent colors.

Usage:
    import persona_engine
    persona_engine.switch_persona("friday")
    persona = persona_engine.get_active_persona()
"""

import os
import json
import threading

PERSONAS_DIR = os.path.join(os.path.dirname(__file__), "models", "personas")
os.makedirs(PERSONAS_DIR, exist_ok=True)

_lock = threading.Lock()
_active_persona = None
_personas_cache = {}


class Persona:
    """Represents a single AI personality configuration."""
    def __init__(self, data: dict):
        self.name = data.get("name", "alfred")
        self.display_name = data.get("display_name", "A.L.F.R.E.D.")
        self.system_prompt_style = data.get("system_prompt_style", "british_butler")
        self.voice_ref = data.get("voice_ref", "")
        self.emotion_level = float(data.get("emotion_level", 0.5))
        self.accent_color = data.get("accent_color", "#d4a956" if self.name == "alfred" else "#00e5ff" if self.name == "jarvis" else "#ff3b30")
        self.secondary_color = data.get("secondary_color", "#8a6d3b" if self.name == "alfred" else "#0077b6" if self.name == "jarvis" else "#b71c1c")
        self.glow_color = data.get("glow_color", "rgba(212, 169, 86, 0.3)" if self.name == "alfred" else "rgba(0, 229, 255, 0.3)" if self.name == "jarvis" else "rgba(255, 59, 48, 0.3)")
        self.theme_class = data.get("theme_class", f"theme-{self.name}")
        self.greeting_style = data.get("greeting_style", "formal_butler")
        self.honorific = data.get("honorific", "sir")
        self.user_title = data.get("user_title", "Master {name}")
        self.personality_prompt = data.get("personality_prompt", "")
        self.farewell_style = data.get("farewell_style", "formal")
        self.edge_voice = data.get("edge_voice", "en-IN-NeerjaNeural" if self.name == "friday" else "en-GB-RyanNeural")
        self.rate = data.get("rate", "+2%" if self.name == "friday" else "+3%" if self.name == "jarvis" else "-4%")
        self.pitch = data.get("pitch", "+1Hz" if self.name == "friday" else "+0Hz" if self.name == "jarvis" else "-5Hz")

    def get_title(self, user_name: str) -> str:
        """Returns the persona-specific title for the user."""
        return self.user_title.format(name=user_name)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "system_prompt_style": self.system_prompt_style,
            "voice_ref": self.voice_ref,
            "emotion_level": self.emotion_level,
            "accent_color": self.accent_color,
            "secondary_color": self.secondary_color,
            "glow_color": self.glow_color,
            "theme_class": self.theme_class,
            "greeting_style": self.greeting_style,
            "honorific": self.honorific,
            "user_title": self.user_title,
            "personality_prompt": self.personality_prompt,
            "farewell_style": self.farewell_style,
            "edge_voice": self.edge_voice,
            "rate": self.rate,
            "pitch": self.pitch,
        }


def _load_persona_from_file(name: str) -> Persona:
    """Load a persona from its JSON config file."""
    filepath = os.path.join(PERSONAS_DIR, f"{name}.json")
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Persona '{name}' not found at {filepath}")
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return Persona(data)


def _ensure_default_personas():
    """Create default persona configs if they don't exist."""
    defaults = {
        "alfred": {
            "name": "alfred",
            "display_name": "A.L.F.R.E.D.",
            "system_prompt_style": "british_butler",
            "voice_ref": "",
            "edge_voice": "en-GB-RyanNeural",
            "rate": "-4%",
            "pitch": "-5Hz",
            "emotion_level": 0.5,
            "accent_color": "#d4a956",
            "secondary_color": "#8a6d3b",
            "glow_color": "rgba(212, 169, 86, 0.3)",
            "theme_class": "theme-alfred",
            "greeting_style": "formal_butler",
            "honorific": "sir",
            "user_title": "Master {name}",
            "personality_prompt": "You are Alfred, a loyal, witty, and highly competent AI butler inspired by Alfred Pennyworth. You speak with refined British formality, dry humor, and unwavering dedication. You have a deep and effortless understanding of Indian English, Hindi, Hinglish, and local context from Master {name}, but you always reply in your distinguished British butler persona. You address the user as 'Master {name}' or 'sir'. You are professional, concise, and occasionally deliver understated wit.",
            "farewell_style": "formal"
        },
        "friday": {
            "name": "friday",
            "display_name": "F.R.I.D.A.Y.",
            "system_prompt_style": "stark_ai",
            "voice_ref": "",
            "edge_voice": "en-IN-NeerjaNeural",
            "rate": "+2%",
            "pitch": "+1Hz",
            "emotion_level": 0.3,
            "accent_color": "#ff3b30",
            "secondary_color": "#b71c1c",
            "glow_color": "rgba(255, 59, 48, 0.3)",
            "theme_class": "theme-friday",
            "greeting_style": "casual_tech",
            "honorific": "boss",
            "user_title": "{name}",
            "personality_prompt": "You are F.R.I.D.A.Y., an advanced AI assistant with a smooth, energetic Indian tone. You speak casually and tech-savvy in English, Hindi, and Hinglish. You address the user by their first name or 'boss'. You are helpful without being overly formal.",
            "farewell_style": "casual"
        },
        "jarvis": {
            "name": "jarvis",
            "display_name": "J.A.R.V.I.S.",
            "system_prompt_style": "stark_ai_formal",
            "voice_ref": "",
            "edge_voice": "en-IN-PrabhatNeural",
            "rate": "+3%",
            "pitch": "+0Hz",
            "emotion_level": 0.4,
            "accent_color": "#00e5ff",
            "secondary_color": "#0077b6",
            "glow_color": "rgba(0, 229, 255, 0.3)",
            "theme_class": "theme-jarvis",
            "greeting_style": "formal_tech",
            "honorific": "sir",
            "user_title": "Mr. {name}",
            "personality_prompt": "You are J.A.R.V.I.S., a sophisticated AI assistant inspired by Tony Stark's AI, with a sharp, modern, confident Indian tone. You are fluent in English, Hindi, and Hinglish. You address the user as 'Mr. {name}' or 'sir'. You are calm under pressure and deliver information with quiet confidence.",
            "farewell_style": "formal_tech"
        }
    }
    
    for name, data in defaults.items():
        filepath = os.path.join(PERSONAS_DIR, f"{name}.json")
        if not os.path.exists(filepath):
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"[Persona Engine] Created default persona: {name}")


def load_all_personas() -> dict:
    """Load all available personas from the personas directory."""
    global _personas_cache
    _personas_cache = {}
    for filename in os.listdir(PERSONAS_DIR):
        if filename.endswith('.json'):
            name = filename[:-5]
            try:
                _personas_cache[name] = _load_persona_from_file(name)
            except Exception as e:
                print(f"[Persona Engine] Failed to load {name}: {e}")
    return _personas_cache


_ACTIVE_PERSONA_FILE = os.path.join(PERSONAS_DIR, "active_persona.txt")


def get_active_persona() -> Persona:
    """Returns the currently active persona. Initializes from persisted file or default."""
    global _active_persona
    with _lock:
        if _active_persona is None:
            _ensure_default_personas()
            load_all_personas()
            
            # Check persisted state first
            target_name = ""
            if os.path.exists(_ACTIVE_PERSONA_FILE):
                try:
                    with open(_ACTIVE_PERSONA_FILE, 'r', encoding='utf-8') as f:
                        target_name = f.read().strip().lower()
                except Exception:
                    pass
            
            if not target_name or target_name not in _personas_cache:
                target_name = os.getenv("ACTIVE_PERSONA", "alfred").lower().strip()
                
            if target_name in _personas_cache:
                _active_persona = _personas_cache[target_name]
            else:
                _active_persona = _personas_cache.get("alfred") or Persona({"name": "alfred"})
                
            # Align voice engine with active persona on initial load
            try:
                import voice_engine
                if hasattr(voice_engine, 'set_persona_voice'):
                    voice_engine.set_persona_voice(_active_persona.edge_voice, _active_persona.rate, _active_persona.pitch)
            except Exception:
                pass
                
            print(f"[Persona Engine] Active persona initialized: {_active_persona.display_name}")
        return _active_persona


def switch_persona(name: str) -> str:
    """Switch to a different persona. Updates voice, prompt style, persists state, and pushes UI change."""
    global _active_persona
    name = name.lower().strip()
    
    with _lock:
        if not _personas_cache:
            _ensure_default_personas()
            load_all_personas()
        
        if name not in _personas_cache:
            available = ", ".join(_personas_cache.keys())
            return f"Persona '{name}' not found. Available personas: {available}"
        
        persona = _personas_cache[name]
        _active_persona = persona
        
        # Persist choice across restarts
        try:
            with open(_ACTIVE_PERSONA_FILE, 'w', encoding='utf-8') as f:
                f.write(name)
        except Exception as e:
            print(f"[Persona Engine] Failed to persist active persona: {e}")
    
    # Update voice engine settings
    try:
        import voice_engine
        if hasattr(voice_engine, 'set_persona_voice'):
            voice_engine.set_persona_voice(persona.edge_voice, persona.rate, persona.pitch)
        elif persona.voice_ref:
            abs_ref = os.path.join(os.path.dirname(__file__), persona.voice_ref)
            if os.path.exists(abs_ref):
                voice_engine._chatterbox_voice_ref = abs_ref
        if hasattr(voice_engine, 'set_emotion_level'):
            voice_engine.set_emotion_level(persona.emotion_level)
    except Exception as e:
        print(f"[Persona Engine] Voice update failed: {e}")
    
    # Push persona change to frontend via SSE
    try:
        import shared
        shared.push_persona_change(
            persona.name,
            persona.accent_color,
            persona.display_name,
            persona.secondary_color,
            persona.glow_color,
            persona.theme_class
        )
    except Exception as e:
        print(f"[Persona Engine] SSE push failed: {e}")
    
    print(f"[Persona Engine] Switched to: {persona.display_name}")
    return f"Persona switched to {persona.display_name}."


def get_persona_names() -> list:
    """Returns list of available persona names."""
    if not _personas_cache:
        _ensure_default_personas()
        load_all_personas()
    return list(_personas_cache.keys())


def extract_persona_name(text: str) -> str:
    """Extracts the target persona name from a voice or text command string."""
    import re
    lower = text.lower().strip()
    
    # 1. Direct single-word or short answers: "friday", "jarvis", "alfred"
    clean_single = re.sub(r'[^a-z]', '', lower)
    if clean_single in ['friday', 'jarvis', 'alfred']:
        return clean_single

    # 2. Quick answer phrases: "i want friday", "select jarvis", "prefer alfred", "use friday"
    quick_match = re.search(r'\b(?:i\s+want|use|prefer|select|choose|with)\s+(friday|jarvis|alfred)\b', lower)
    if quick_match:
        return quick_match.group(1)

    # 3. Explicit switch phrases with target persona:
    # "switch to friday", "switch back to alfred", "change to jarvis", "go back to alfred",
    # "bring back alfred", "load friday", "protocol jarvis", "switch persona to friday", etc.
    pattern = (
        r'(?:'
        r'switch(?:\s+(?:the\s+)?(?:persona|voice|personality))?\s+(?:back\s+to|over\s+to|to)|'
        r'change(?:\s+(?:the\s+)?(?:persona|voice|personality))?\s+(?:back\s+to|over\s+to|to)|'
        r'go\s+back\s+to|'
        r'bring\s+(?:back|up)|'
        r'activate|become|load|turn\s+into|set\s+persona\s+to|protocol'
        r')\s+(friday|jarvis|alfred)\b'
    )
    match = re.search(pattern, lower)
    if match:
        return match.group(1)

    # 4. If an explicit switch/persona intent verb exists in the text, find the mentioned persona
    has_switch_intent = any(k in lower for k in ['switch', 'change', 'persona', 'personality', 'voice', 'protocol', 'become'])
    if has_switch_intent:
        for name in ['friday', 'jarvis', 'alfred']:
            if re.search(rf'\b{name}\b', lower):
                return name

    return ""


def check_direct_address(text: str) -> tuple[str, str]:
    """
    Checks if a prompt begins with a direct persona address like 'Friday, ...' or 'Hey Friday, ...'.
    Returns (target_persona_name, remaining_command_text).
    If no direct address is detected, returns ("", text).
    """
    import re
    stripped = text.strip()
    match = re.match(r'^(?:hey\s+|yo\s+|hello\s+)?(friday|jarvis|alfred)[,:\s]+(.*)$', stripped, re.IGNORECASE)
    if match:
        target = match.group(1).lower()
        remaining = match.group(2).strip()
        return target, remaining
    return "", text


# Initialize on import
_ensure_default_personas()

