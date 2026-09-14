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
        self.accent_color = data.get("accent_color", "#00b4d8")
        self.greeting_style = data.get("greeting_style", "formal_butler")
        self.honorific = data.get("honorific", "sir")
        self.user_title = data.get("user_title", "Master {name}")
        self.personality_prompt = data.get("personality_prompt", "")
        self.farewell_style = data.get("farewell_style", "formal")

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
            "greeting_style": self.greeting_style,
            "honorific": self.honorific,
            "user_title": self.user_title,
            "personality_prompt": self.personality_prompt,
            "farewell_style": self.farewell_style,
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
            "emotion_level": 0.5,
            "accent_color": "#00b4d8",
            "greeting_style": "formal_butler",
            "honorific": "sir",
            "user_title": "Master {name}",
            "personality_prompt": "You are Alfred, a loyal, witty, and highly competent AI butler inspired by Alfred Pennyworth. You speak with refined British formality, dry humor, and unwavering dedication. You address the user as 'Master {name}' or 'sir'. You are professional, concise, and occasionally deliver understated wit.",
            "farewell_style": "formal"
        },
        "friday": {
            "name": "friday",
            "display_name": "F.R.I.D.A.Y.",
            "system_prompt_style": "stark_ai",
            "voice_ref": "",
            "emotion_level": 0.3,
            "accent_color": "#ff6b35",
            "greeting_style": "casual_tech",
            "honorific": "boss",
            "user_title": "{name}",
            "personality_prompt": "You are F.R.I.D.A.Y., an advanced AI assistant inspired by Tony Stark's AI. You are efficient, direct, and tech-savvy. You speak casually but professionally, using modern tech terminology. You address the user by their first name or 'boss'. You are helpful without being overly formal. You occasionally reference system diagnostics and technical specs.",
            "farewell_style": "casual"
        },
        "jarvis": {
            "name": "jarvis",
            "display_name": "J.A.R.V.I.S.",
            "system_prompt_style": "stark_ai_formal",
            "voice_ref": "",
            "emotion_level": 0.4,
            "accent_color": "#4cc9f0",
            "greeting_style": "formal_tech",
            "honorific": "sir",
            "user_title": "Mr. {name}",
            "personality_prompt": "You are J.A.R.V.I.S., a sophisticated AI assistant inspired by Tony Stark's original AI. You are elegant, precise, and carry a refined British accent in your speech patterns. You are more formal than FRIDAY but more tech-oriented than Alfred. You address the user as 'Mr. {name}' or 'sir'. You are calm under pressure and deliver information with quiet confidence.",
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


def get_active_persona() -> Persona:
    """Returns the currently active persona. Initializes to default if needed."""
    global _active_persona
    with _lock:
        if _active_persona is None:
            _ensure_default_personas()
            load_all_personas()
            default_name = os.getenv("ACTIVE_PERSONA", "alfred").lower().strip()
            if default_name in _personas_cache:
                _active_persona = _personas_cache[default_name]
            else:
                _active_persona = _personas_cache.get("alfred") or Persona({"name": "alfred"})
            print(f"[Persona Engine] Active persona: {_active_persona.display_name}")
        return _active_persona


def switch_persona(name: str) -> str:
    """Switch to a different persona. Updates voice, prompt style, and pushes UI change."""
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
    
    # Update voice engine settings
    try:
        import voice_engine
        if persona.voice_ref:
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
        shared.push_persona_change(persona.name, persona.accent_color, persona.display_name)
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
    """Extracts the target persona name from a voice command string."""
    lower = text.lower()
    for name in ['friday', 'jarvis', 'alfred']:
        if name in lower:
            return name
    return ""


# Initialize on import
_ensure_default_personas()
