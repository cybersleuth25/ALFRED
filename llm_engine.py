import ollama
import json
import os
import sys
import re
import time
import random
from datetime import datetime

# Add the root directory to path to ensure we can import tools & memory_engine normally
sys.path.append(os.path.dirname(__file__))
from tools import core_tools
import memory_engine
import shared

# ── Pre-compiled Regex Patterns (compiled once at module load) ──
_RE_BRIGHTNESS = re.compile(r'(?:set |change )?brightness (?:to |at )?(\d+)')
_RE_CLOSE_TAB = re.compile(r'close (?:the )?(.+?) tab')
_RE_SWITCH_TAB = re.compile(r'switch to (?:the )?(.+?) tab')
_RE_WHATSAPP = re.compile(r'(?:whatsapp|message)\s+(?:to\s+)?(?:my\s+)?(.+?)\s+(?:saying|that|say)\s+(.+)', re.IGNORECASE)
_RE_WHATSAPP_SIMPLE = re.compile(r'(?:whatsapp|message)\s+(?:to\s+)?(?:my\s+)?(\w+)\s+(.+)', re.IGNORECASE)
_RE_REMINDER = re.compile(r'remind me (?:to|about)?\s+(.+)\s+in\s+(\d+)\s+min', re.IGNORECASE)
_RE_KNOWLEDGE = re.compile(r'^(who|what|where|when|why|how|which|tell me|explain|describe)\b\s+(.+)', re.IGNORECASE)

# ── Tool Signal Keywords (checked to decide if a prompt needs tool access) ──
_TOOL_SIGNAL_WORDS = frozenset([
    # Weather
    'weather', 'temperature', 'rain', 'forecast', 'hot', 'cold',
    # Tasks & Reminders
    'remind', 'reminder', 'alarm', 'task', 'tasks', 'todo',
    'journal', 'diary', 'write', 'note',
    # File Operations
    'file', 'create', 'delete', 'rename', 'move', 'open',
    # Time & Scheduling
    'time', 'date', 'schedule',
    # Memory
    'remember', 'forget', 'learn', 'fact', 'earlier',
    'screen history', 'seen on screen', 'looking at earlier',
    # System Control
    'launch', 'start', 'mute', 'unmute', 'volume',
    # Media
    'play', 'song', 'music', 'pause', 'resume', 'skip',
    'next track', 'previous', 'now playing', 'currently playing', 'spotify',
    # Messaging
    'whatsapp', 'message', 'text', 'send',
    # Search & Research
    'search', 'google', 'look up', 'find out', 'deep dive', 'deep research', 'swarm',
    # News & OSINT
    'news', 'headlines', 'briefing', 'earthquake', 'quake',
    'email', 'mail', 'osint', 'social media', 'account',
    # System Hardware
    'battery', 'brightness', 'wifi', 'bluetooth', 'lock', 'sleep', 'shutdown', 'screenshot',
    # Browser
    'tab', 'tabs', 'browser',
    # Web Fetch
    'fetch', 'read url', 'scrape', 'website', 'url', 'link',
    # Vision & Input Control
    'mouse', 'click', 'type', 'keyboard', 'press', 'screen', 'see', 'vision',
    # Civic
    'crop', 'crops', 'dam', 'reservoir', 'civic', 'alerts',
    'health score', 'updates', 'health', 'healthcare',
    'look', 'holding',
])

# Wire up the recall_memories tool (avoids circular import since core_tools loads first)
# This runs at import-time, after both modules are available
core_tools.TOOL_REGISTRY["recall_memories"] = lambda query="": __import__('llm_engine').recall_memories(query)

# --- Configuration ---
from dotenv import load_dotenv
load_dotenv()
USER_NAME = os.getenv("ALFRED_USER_NAME", "User")

# --- Brain Access ---
def chat(messages, options=None, format=None):
    """Unified chat function for external modules to use the active brain."""
    client, model_name = shared.get_brain()
    try:
        res = client.chat(
            model=model_name,
            messages=messages,
            options=options or {},
            format=format,
            keep_alive='1h'
        )
        return res
    except Exception as e:
        print(f"[LLM] Chat failed: {e}")
        raise e


# --- Instant canned responses (NO LLM call, 0 seconds) ---
_GREETINGS = {
    'hello': ["Good day, Master {name}. How may I be of service?", "Hello, sir. At your disposal, as always."],
    'hi': ["Good day, sir. What can I do for you?", "Hello, Master {name}. How may I assist?"],
    'hey': ["Greetings, sir. How may I help?", "At your service, Master {name}."],
    'how are you': ["Quite well, thank you, Master {name}. And yourself?", "Functioning splendidly, sir. How may I assist you today?"],
    'good morning': ["A fine morning indeed, Master {name}. What shall we tackle today?", "Good morning, sir. I trust you slept well."],
    'good evening': ["Good evening, Master {name}. How may I be of assistance?", "A pleasant evening to you, sir."],
    'good night': ["Good night, Master {name}. Rest well, sir.", "Pleasant dreams, sir. I shall keep watch."],
    'thank you': ["You're most welcome, sir.", "My pleasure entirely, Master {name}.", "Happy to help, sir."],
    'thanks': ["You're welcome, sir.", "Of course, Master {name}.", "Anytime, sir."],
    'what can you do': ["I can check the weather, manage your reminders, handle files, keep a journal, and of course, provide sparkling conversation, sir.", "Quite a lot, sir. Weather, reminders, file management, journaling, and witty banter."],
    'who are you': ["I am Alfred, your personal AI butler, sir. At your service.", "Alfred, sir. Your loyal digital valet."],
}

def _get_canned_response(prompt: str):
    """Return instant response for common phrases, or None."""
    lower = prompt.lower().strip().rstrip('?!.,')
    # Use word matching to prevent 'hi' triggering on 'Chikkamagaluru'
    words = lower.split()
    
    for key, responses in _GREETINGS.items():
        if lower == key or lower.startswith(f"{key} ") or key in words:
            return random.choice(responses).format(name=USER_NAME)
    return None

# --- Semantic Memory Helpers ---
_TRIVIAL_PATTERNS = {
    'hello', 'hi', 'hey', 'thanks', 'thank you', 'ok', 'okay', 'bye',
    'good morning', 'good evening', 'good night', 'good afternoon',
    'how are you', 'what can you do', 'who are you', 'yes', 'no', 'sure',
    'go to sleep', 'standby', 'dismissed', 'sleep', 'exit', 'quit',
}

def _should_remember(user_msg: str, alfred_response: str) -> bool:
    """Determines if a conversation exchange is worth storing in semantic memory."""
    lower = user_msg.lower().strip().rstrip('?!.,')
    # Skip trivial exchanges
    if lower in _TRIVIAL_PATTERNS:
        return False
    # Skip very short exchanges (likely greetings or one-word answers)
    if len(user_msg.split()) < 3 and len(alfred_response.split()) < 5:
        return False
    # Skip tool-only fast-path responses that just echo data
    if alfred_response.startswith("Here's what I found"):
        return False
    # Skip error responses
    if 'error' in alfred_response.lower()[:30]:
        return False
    return True

def _auto_save_memory(user_msg: str, alfred_response: str):
    """Silently stores a conversation exchange in semantic memory if it's meaningful."""
    if not _should_remember(user_msg, alfred_response):
        return
    try:
        # Combine user message and response into a single memory chunk
        memory_text = f"User asked: {user_msg}. Alfred responded: {alfred_response[:200]}"
        memory_engine.store_memory(memory_text, category='conversation')
    except Exception as e:
        print(f"[Memory] Auto-save failed (non-critical): {e}")

def recall_memories(query: str) -> str:
    """Searches Alfred's semantic memory for information relevant to the query."""
    results = memory_engine.search_memories(query, top_k=5)
    if not results:
        return "No relevant memories found."
    output = "Relevant memories:\n"
    for r in results:
        output += f"- {r['content']} (similarity: {r['similarity']}, from: {r['created_at'][:10]})\n"
    return output.strip()

# --- Tool keywords for fast-path detection ---
_TOOL_KEYWORDS = {
    'weather': 'check_weather', 'temperature': 'check_weather', 'rain': 'check_weather',
    'hot': 'check_weather', 'cold': 'check_weather', 'forecast': 'check_weather',
    'journal': 'read_journal', 'diary': 'read_journal',
    'earthquake': 'get_earthquakes', 'quake': 'get_earthquakes', 'seismic': 'get_earthquakes',
    'briefing': 'daily_briefing', 'brief me': 'daily_briefing', 'intelligence': 'daily_briefing',
    'news': 'daily_briefing', 'headlines': 'daily_briefing', 'brief': 'daily_briefing',
    'battery': 'get_battery_status', 'charge': 'get_battery_status',
    'tabs': 'list_browser_tabs', 'tab': 'list_browser_tabs',
    'crop': 'generate_district_health_score', 'dam': 'generate_district_health_score', 'civic': 'generate_district_health_score',
    'reservoir': 'generate_district_health_score', 'alerts': 'generate_district_health_score',
    'health score': 'generate_district_health_score', 'updates': 'generate_district_health_score',
    'healthcare': 'generate_district_health_score', 'health': 'generate_district_health_score',
    'what am i holding': 'analyze_webcam_local', 'what do you see': 'analyze_webcam_local',
    'look at this': 'analyze_webcam_local', 'vision': 'analyze_webcam_local', 'look at me': 'analyze_webcam_local',
    'what is in front': 'analyze_webcam_local'
}

def _detect_tool_shortcut(prompt: str):
    """Check if the user's query obviously maps to a single tool, bypassing LLM for the tool-call step."""
    lower = prompt.lower()
    for keyword, tool_name in _TOOL_KEYWORDS.items():
        if keyword in lower:
            return tool_name
    return None

# --- Sensors ---
def _get_time_of_day() -> str:
    hour = datetime.now().hour
    if 5 <= hour < 12: return "morning"
    elif 12 <= hour < 17: return "afternoon"
    elif 17 <= hour < 21: return "evening"
    else: return "night"

# --- System Prompt & Multi-Agent Defs ---
AGENT_PROFILES = {
    "osint": {
        "role": "You are the OSINT Agent. You handle web searching, fetching URLs, news, weather, real-world data, local civic data, reverse email lookups, and Multi-Agent deep swarm research.",
        "tools": 'check_weather(), search_web(query), get_news(topic?), get_earthquakes(), daily_briefing(), reverse_email_lookup(email), generate_district_health_score(district_slug?), stealth_fetch_url(url), deep_research_swarm(topic)'
    },
    "system": {
        "role": "You are the System Agent. You have full physical control over the desktop (mouse/keyboard) and you CAN see the screen using your analyze_screen tool. YOU MUST USE YOUR TOOLS. If asked to look at the screen, ALWAYS call analyze_screen. If asked to type or press keys, use keyboard_type or keyboard_press.",
        "tools": 'create_file(filepath,content), delete_file(filepath), rename_file(old,new), move_file(src,dest), organize_workspace(dir), launch_application(app), toggle_system_volume(action), play_music(song), get_battery_status(), set_brightness(level), toggle_wifi(action), toggle_bluetooth(action), lock_pc(), sleep_pc(), shutdown_pc(), set_volume(level), take_screenshot(), analyze_screen(query), get_screen_info(), mouse_move_and_click(x,y,button,double_click), keyboard_type(text,press_enter), keyboard_press(key), keyboard_hotkey(key1,key2), learn_new_skill(skill)'
    },
    "memory": {
        "role": "You are the Memory and Scholar Agent. You handle reminders, facts, journaling, and you can query the user's Photographic Screen Memory or local document Library.",
        "tools": 'set_dynamic_reminder(minutes,topic), add_reminder(task,deadline?), list_reminders(), complete_reminder(task_id), delete_reminder(task_id), clear_all_reminders(), remember_fact(fact), forget_fact(fact_id), journal_entry(content), read_journal(), query_library(query), recall_memories(query)'
    },
    "communications": {
        "role": "You are the Communications Agent. You handle sending messages.",
        "tools": 'send_whatsapp(contact_name, message)'
    },
    "browser": {
        "role": "You are the Browser Agent. You control and read browser tabs across Chrome, Edge, and Brave.",
        "tools": 'list_browser_tabs(), close_browser_tab(title), switch_browser_tab(title), open_browser_tab(url), read_browser_tab(title?)'
    }
}

def _build_agent_prompt(agent_name: str) -> str:
    now = datetime.now()
    time_of_day = _get_time_of_day()
    now_str = now.strftime("%A, %B %d, %Y at %I:%M %p")

    context_section = ""
    pending = memory_engine.get_pending_tasks()
    if pending:
        task_lines = "\n".join(f"  ID: {t['id']} | Task: {t['task']} | Added: {t['added_at'][:10]}" for t in pending)
        context_section += f"\nPENDING TASKS:\n{task_lines}"
        
    facts = memory_engine.get_user_facts()
    if facts:
        fact_lines = "\n".join(f"  ID: {f['id']} | Fact: {f['fact']}" for f in facts)
        context_section += f"\nKNOWN FACTS ABOUT MASTER {USER_NAME}:\n{fact_lines}"

    # --- NEW: Inject semantic memories relevant to recent conversation ---
    try:
        if _conversation_history:
            last_user_msg = ""
            for msg in reversed(_conversation_history):
                if msg['role'] == 'user':
                    last_user_msg = msg['content']
                    break
            if last_user_msg:
                relevant_memories = memory_engine.search_memories(last_user_msg, top_k=3)
                if relevant_memories:
                    mem_lines = "\n".join(f"  - {m['content']}" for m in relevant_memories)
                    context_section += f"\nRELEVANT MEMORIES (from past interactions):\n{mem_lines}"
    except Exception:
        pass  # Non-critical — don't break the agent if memory search fails

    profile = AGENT_PROFILES.get(agent_name, AGENT_PROFILES["osint"])
    
    # Dynamically inject learned skills into the system agent
    agent_tools = profile['tools']
    if agent_name == "system":
        try:
            sandbox_dir = os.path.join(os.path.dirname(__file__), "Alfred_Workspace", "sandbox_skills")
            if os.path.exists(sandbox_dir):
                funcs = [f[:-3] for f in os.listdir(sandbox_dir) if f.endswith(".py") and not f.startswith("__")]
                if funcs:
                    custom_tools_str = ", ".join([f"{f}()" for f in funcs])
                    agent_tools += f", {custom_tools_str}"
        except Exception:
            pass

    user_home = os.path.expanduser("~").replace("\\", "/")
    workspace_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "Alfred_Workspace")).replace("\\", "/")
    
    return f"""{profile['role']} You are a sub-agent of Alfred running on Master {USER_NAME}'s computer.
Date: {now_str} ({time_of_day}){context_section}

OUTPUT FORMAT RULES:
1. You MUST output ONLY raw, valid JSON. 
2. DO NOT wrap your output in ```json or ``` markdown blocks.
3. DO NOT output any conversational text outside of the JSON object.
4. STRICT LENGTH LIMITS: Keep 'thought' extremely short. Keep 'response' under 1-2 sentences. DO NOT hallucinate or add imaginary text.
Schema: {{"thought": "your reasoning", "tools_to_call": [{{"tool": "tool_name", "kwargs": {{"param_name": "value"}} }}], "response": "spoken text only if finished"}}
Tools: {agent_tools}
Paths: Downloads={user_home}/Downloads/ Documents={user_home}/Documents/ Workspace={workspace_path}/
Rules: You are software. Be concise, factual, and think step-by-step in the 'thought' field before acting."""

# --- Conversation History (Persistent across sessions via SQLite) ---
_conversation_history = memory_engine.load_recent_history(20)
print(f"[System] Loaded {len(_conversation_history)} conversation turns from previous sessions.")
_MAX_HISTORY = 20  # Prevent unbounded memory growth

def _needs_tools(prompt: str) -> bool:
    """Check if the prompt likely needs tool access."""
    lower = prompt.lower()
    return any(word in lower for word in _TOOL_SIGNAL_WORDS)

def _fast_respond(prompt: str, speech: str, t0: float, save_memory: bool = True, tts_callback=None) -> str:
    """Common handler for all fast-path responses. Logs, saves history, and returns."""
    global _conversation_history
    _conversation_history.append({'role': 'user', 'content': prompt})
    _conversation_history.append({'role': 'assistant', 'content': speech})
    memory_engine.save_conversation_turn('user', prompt)
    memory_engine.save_conversation_turn('assistant', speech)
    if save_memory:
        _auto_save_memory(prompt, speech)
    print(f"\n[Alfred says]: {speech}  ({time.time()-t0:.1f}s)")
    if tts_callback:
        tts_callback(speech)
    return speech

def generate_response(prompt: str, tts_callback=None) -> str:
    global _conversation_history
    t0 = time.time()
    print("\n[Alfred is thinking...]")
    
    lower_prompt = prompt.lower().strip()

    # ── PATH -1: PROTOCOL OMEGA CONFIRMATION ──
    if getattr(shared, 'awaiting_study_confirmation', False):
        shared.awaiting_study_confirmation = False
        if any(w in lower_prompt for w in ['yes', 'yeah', 'sure', 'do it', 'confirm', 'start']):
            import study_mentor
            res = study_mentor.activate()
            return _fast_respond(prompt, res, t0, tts_callback=tts_callback)
        else:
            return _fast_respond(prompt, "Very well, sir. Protocol Omega remains on standby.", t0, tts_callback=tts_callback)

    # ── PATH -0.5: START PROTOCOL OMEGA INTENT ──
    if any(phrase in lower_prompt for phrase in ['i am studying', 'time to study', 'start protocol omega', 'study mode']):
        import study_mentor
        if study_mentor.is_active():
            return _fast_respond(prompt, "Protocol Omega is already active, sir.", t0, tts_callback=tts_callback)
        shared.awaiting_study_confirmation = True
        return _fast_respond(prompt, "Shall I initiate Protocol Omega, sir?", t0, save_memory=False, tts_callback=tts_callback)

    # ── PATH -0.4: STOP PROTOCOL OMEGA INTENT ──
    if any(phrase in lower_prompt for phrase in ['stop studying', 'stop protocol omega', 'deactivate protocol omega']):
        import study_mentor
        if study_mentor.is_active():
            res = study_mentor.deactivate()
            return _fast_respond(prompt, res, t0, tts_callback=tts_callback)
        else:
            return _fast_respond(prompt, "Protocol Omega is not currently active, sir.", t0, tts_callback=tts_callback)

    # ── PATH 0: INSTANT — canned response, ZERO LLM calls ──
    canned = _get_canned_response(prompt)
    if canned:
        print(f"[Instant-path] Canned response, no LLM needed.")
        return _fast_respond(prompt, canned, t0, save_memory=False, tts_callback=tts_callback)

    # ── PATH 1: FAST TOOL PATH — obvious tool keyword, NO LLM at all ──
    shortcut_tool = _detect_tool_shortcut(prompt)
    if shortcut_tool:
        print(f"[Fast-path] Detected tool shortcut: {shortcut_tool}")
        tool_result = core_tools.execute_tool(shortcut_tool, {})
        print(f"       Result: {tool_result}")
        return _fast_respond(prompt, f"Here's what I found, sir. {tool_result}", t0, tts_callback=tts_callback)

    # ── PATH 1.5: FAST APP LAUNCH (handles "open X and play Y" too) ──
    if lower_prompt.startswith("open ") or lower_prompt.startswith("launch ") or lower_prompt.startswith("start "):
        rest = lower_prompt.split(" ", 1)[1].strip("., ")
        
        # Handle compound: "open spotify and play believer by imagine dragons"
        if " and play " in rest:
            app_part, song_part = rest.split(" and play ", 1)
            app_part = app_part.strip()
            song_part = song_part.strip()
            
            print(f"[Fast-path] Compound command: open '{app_part}' + play '{song_part}'")
            core_tools.execute_tool("launch_application", {"app_name": app_part})
            core_tools.execute_tool("play_music", {"song_query": song_part})
            return _fast_respond(prompt, f"Opening {app_part} and playing {song_part} for you, sir.", t0, tts_callback=tts_callback)
        
        app_name = rest
        print(f"[Fast-path] Detected app launch: {app_name}")
        core_tools.execute_tool("launch_application", {"app_name": app_name})
        return _fast_respond(prompt, f"Right away, sir. Opening {app_name}.", t0, tts_callback=tts_callback)

    # ── PATH 1.6: FAST MUSIC PLAY ──
    if lower_prompt.startswith("play "):
        song_query = lower_prompt.split(" ", 1)[1].strip("., ")
        print(f"[Fast-path] Detected music request: {song_query}")
        core_tools.execute_tool("play_music", {"song_query": song_query})
        return _fast_respond(prompt, f"Playing {song_query} for you, sir.", t0, tts_callback=tts_callback)

    # ── PATH 1.65: SPOTIFY PLAYBACK CONTROLS ──
    _spotify_now_playing_keywords = ['what am i playing', 'what\'s playing', 'whats playing', 'what am i listening', 'currently playing', 'now playing', 'what song is this', 'which song', 'on spotify']
    _spotify_pause_keywords = ['pause music', 'pause spotify', 'pause the music', 'stop music', 'stop spotify', 'stop the music', 'pause playback', 'pause']
    _spotify_resume_keywords = ['resume music', 'resume spotify', 'resume the music', 'continue music', 'continue playing', 'unpause', 'resume playback', 'resume']
    _spotify_skip_keywords = ['skip', 'next song', 'next track', 'skip song', 'skip track', 'skip this', 'play next']
    _spotify_prev_keywords = ['previous song', 'previous track', 'go back', 'last song', 'play previous', 'previous']

    if any(kw in lower_prompt for kw in _spotify_now_playing_keywords):
        print(f"[Fast-path] Spotify: get now playing")
        tool_result = core_tools.execute_tool("get_now_playing", {})
        return _fast_respond(prompt, tool_result, t0, tts_callback=tts_callback)

    if any(kw in lower_prompt for kw in _spotify_pause_keywords):
        print(f"[Fast-path] Spotify: pause")
        core_tools.execute_tool("spotify_pause", {})
        return _fast_respond(prompt, "Music paused, sir.", t0, tts_callback=tts_callback)

    if any(kw in lower_prompt for kw in _spotify_resume_keywords):
        print(f"[Fast-path] Spotify: resume")
        core_tools.execute_tool("spotify_resume", {})
        return _fast_respond(prompt, "Resuming playback, sir.", t0, tts_callback=tts_callback)

    if any(kw in lower_prompt for kw in _spotify_skip_keywords):
        print(f"[Fast-path] Spotify: skip")
        core_tools.execute_tool("spotify_skip", {})
        return _fast_respond(prompt, "Skipping to the next track, sir.", t0, tts_callback=tts_callback)

    if any(kw in lower_prompt for kw in _spotify_prev_keywords):
        print(f"[Fast-path] Spotify: previous")
        core_tools.execute_tool("spotify_previous", {})
        return _fast_respond(prompt, "Going back to the previous track, sir.", t0, tts_callback=tts_callback)

    # ── PATH 1.7: FAST WHATSAPP ──
    if "whatsapp" in lower_prompt or ("message" in lower_prompt and ("to " in lower_prompt or "mom" in lower_prompt or "dad" in lower_prompt)):
        match = _RE_WHATSAPP.search(lower_prompt)
        if not match:
            match = _RE_WHATSAPP_SIMPLE.search(lower_prompt)
        
        if match:
            contact = match.group(1).strip("., ")
            message = match.group(2).strip()
            print(f"[Fast-path] WhatsApp to '{contact}': '{message}'")
            tool_result = core_tools.execute_tool("send_whatsapp", {"contact_name": contact, "message": message})
            return _fast_respond(prompt, tool_result, t0, tts_callback=tts_callback)

    # ── PATH 1.8: FAST REMINDERS ──
    if lower_prompt.startswith("remind me"):
        match = _RE_REMINDER.search(lower_prompt)
        if match:
            topic = match.group(1).strip()
            minutes = match.group(2).strip()
            print(f"[Fast-path] Detected reminder: '{topic}' in {minutes} min")
            core_tools.execute_tool("set_dynamic_reminder", {"minutes": minutes, "topic": topic})
            return _fast_respond(prompt, f"Right away, sir. I will remind you to {topic} in {minutes} minutes.", t0, tts_callback=tts_callback)

    # ── PATH 1.85: GLOBE VIEW (3D World Intelligence) ──
    globe_show_triggers = ['show me the world', 'show the world', 'show globe', 'open globe',
                           'world view', 'show map', 'earthquake map', 'global view',
                           'show earth', 'open the globe', 'tell me about the world']
    globe_hide_triggers = ['hide globe', 'close globe', 'hide map', 'close map', 'back to chat']
    
    if any(trigger in lower_prompt for trigger in globe_show_triggers):
        print(f"[Fast-path] Globe view → SHOW")
        shared.push_globe(True)
        return _fast_respond(prompt, "Here's your global intelligence view, sir. You can see live earthquake activity and data points around the world.", t0, tts_callback=tts_callback)
    
    if any(trigger in lower_prompt for trigger in globe_hide_triggers):
        print(f"[Fast-path] Globe view → HIDE")
        shared.push_globe(False)
        return _fast_respond(prompt, "Returning to standard view, sir.", t0, tts_callback=tts_callback)

    # ── PATH 1.855: SMART MIRROR VIEW ──
    mirror_show_triggers = ['smart mirror', 'mirror mode', 'activate mirror', 'turn on mirror']
    mirror_hide_triggers = ['exit mirror', 'close mirror', 'disable mirror', 'turn off mirror', 'normal mode']
    
    if any(trigger in lower_prompt for trigger in mirror_show_triggers):
        print(f"[Fast-path] Mirror view → SHOW")
        shared.push_mirror_mode(True)
        return _fast_respond(prompt, "Activating Smart Mirror interface, sir.", t0, tts_callback=tts_callback)
    
    if any(trigger in lower_prompt for trigger in mirror_hide_triggers):
        print(f"[Fast-path] Mirror view → HIDE")
        shared.push_mirror_mode(False)
        return _fast_respond(prompt, "Deactivating Smart Mirror interface, sir.", t0, tts_callback=tts_callback)

    # ── PATH 1.86: FAST OS CONTROL ──
    _os_fast_paths = {
        'lock my pc': ('lock_pc', {}), 'lock the pc': ('lock_pc', {}), 'lock computer': ('lock_pc', {}), 'lock my computer': ('lock_pc', {}),
        'go to sleep': ('sleep_pc', {}), 'sleep mode': ('sleep_pc', {}), 'put pc to sleep': ('sleep_pc', {}),
        'take a screenshot': ('take_screenshot', {}), 'screenshot': ('take_screenshot', {}), 'take screenshot': ('take_screenshot', {}),
        'cancel shutdown': ('cancel_shutdown', {}), 'stop shutdown': ('cancel_shutdown', {}),
    }
    for trigger, (tool_name, kwargs) in _os_fast_paths.items():
        if trigger in lower_prompt:
            print(f"[Fast-path] OS Control: {tool_name}")
            tool_result = core_tools.execute_tool(tool_name, kwargs)
            return _fast_respond(prompt, f"Done, sir. {tool_result}", t0, tts_callback=tts_callback)

    brightness_match = _RE_BRIGHTNESS.search(lower_prompt)
    if brightness_match:
        level = brightness_match.group(1)
        print(f"[Fast-path] Set brightness to {level}")
        tool_result = core_tools.execute_tool("set_brightness", {"level": level})
        return _fast_respond(prompt, f"Right away, sir. {tool_result}", t0, tts_callback=tts_callback)

    # ── PATH 1.88: FAST WIFI/BLUETOOTH TOGGLE ──
    if 'wifi' in lower_prompt or 'wi-fi' in lower_prompt:
        action = 'disable' if any(w in lower_prompt for w in ['off', 'disable', 'turn off', 'disconnect']) else 'enable'
        print(f"[Fast-path] WiFi → {action}")
        tool_result = core_tools.execute_tool("toggle_wifi", {"action": action})
        return _fast_respond(prompt, f"Done, sir. {tool_result}", t0, tts_callback=tts_callback)

    if 'bluetooth' in lower_prompt:
        action = 'disable' if any(w in lower_prompt for w in ['off', 'disable', 'turn off', 'disconnect']) else 'enable'
        print(f"[Fast-path] Bluetooth → {action}")
        tool_result = core_tools.execute_tool("toggle_bluetooth", {"action": action})
        return _fast_respond(prompt, f"Done, sir. {tool_result}", t0, tts_callback=tts_callback)

    # ── PATH 1.89: FAST BROWSER TAB COMMANDS ──
    close_tab_match = _RE_CLOSE_TAB.search(lower_prompt)
    if close_tab_match:
        title = close_tab_match.group(1).strip()
        print(f"[Fast-path] Close tab: '{title}'")
        tool_result = core_tools.execute_tool("close_browser_tab", {"title": title})
        return _fast_respond(prompt, f"Done, sir. {tool_result}", t0, tts_callback=tts_callback)

    switch_tab_match = _RE_SWITCH_TAB.search(lower_prompt)
    if switch_tab_match:
        title = switch_tab_match.group(1).strip()
        print(f"[Fast-path] Switch tab: '{title}'")
        tool_result = core_tools.execute_tool("switch_browser_tab", {"title": title})
        return _fast_respond(prompt, f"Done, sir. {tool_result}", t0, tts_callback=tts_callback)


    # ── PATH 1.9: FAST WEB SEARCH ──
    if lower_prompt.startswith("search ") or lower_prompt.startswith("google ") or lower_prompt.startswith("look up "):
        query = lower_prompt.split(" ", 1)[1].strip("., ")
        # Remove filler like "for" at the start
        if query.startswith("for "):
            query = query[4:].strip()
        
        print(f"[Fast-path] Web search: '{query}'")
        tool_result = core_tools.execute_tool("search_web", {"query": query})
        return _fast_respond(prompt, f"Here's what I found on the web, sir. {tool_result}", t0, tts_callback=tts_callback)

    # ── PATH 1.10: KNOWLEDGE QUESTIONS → AUTO WEB SEARCH ──
    _self_refs = ['yourself', 'you', 'alfred', 'your name', 'your job', 'your purpose',
                  ' my ', 'my ', ' me ', 'me?', 'about me', ' i ']
    is_self_question = any(ref in f' {lower_prompt} ' for ref in _self_refs)
    
    knowledge_match = _RE_KNOWLEDGE.match(lower_prompt)
    if knowledge_match and not is_self_question:
        query = knowledge_match.group(2).strip("?!., ")
        prefix = knowledge_match.group(1).strip()
        
        print(f"[Fast-path] Knowledge question: '{prefix} {query}' → web search")
        tool_result = core_tools.execute_tool("search_web", {"query": f"{prefix} {query}"})

        if "No web results" in tool_result or "failed" in tool_result.lower():
            print("[Fast-path] Web search returned nothing, falling through to chat path.")
        else:
            return _fast_respond(prompt, f"Here's what I found, sir. {tool_result}", t0, tts_callback=tts_callback)

    # ── PATH 2: CHAT PATH — no tools needed, lightweight LLM conversation ──
    if not _needs_tools(prompt):
        print("[Chat-path] Simple conversation, using lightweight LLM.")
        # Cap conversation history to prevent unbounded memory growth
        if len(_conversation_history) > _MAX_HISTORY:
            _conversation_history = _conversation_history[-_MAX_HISTORY:]
        _conversation_history.append({'role': 'user', 'content': prompt})

        # Inject semantic memories into chat context
        memory_section = ""
        try:
            relevant_memories = memory_engine.search_memories(prompt, top_k=3)
            if relevant_memories:
                mem_lines = "\n".join(f"  - {m['content']}" for m in relevant_memories)
                memory_section = f"\nRELEVANT MEMORIES (from past interactions):\n{mem_lines}"
        except Exception:
            pass

        facts = memory_engine.get_user_facts()
        facts_section = ""
        if facts:
            fact_lines = "\n".join(f"  - {f['fact']}" for f in facts)
            facts_section = f"\nKNOWN FACTS ABOUT MASTER {USER_NAME}:\n{fact_lines}"

        client, model_name = shared.get_brain()
        
        chat_system = f"""You are Alfred, an AI software assistant with a British butler persona running on Master {USER_NAME}'s computer. You are powered by the {model_name} model running 100% offline via Ollama. You cannot perform physical tasks.

CRITICAL ANTI-HALLUCINATION RULES:
1. You must NEVER fabricate, guess, or hallucinate information. No imaginary replies.
2. If asked a factual question, historical detail, or current event that you are not 100% certain about, you MUST reply with exactly: "I am not certain about that, sir. Shall I search the web for you?"
3. Do not attempt to guess names, dates, or facts.
4. Master {USER_NAME} lives in {os.getenv("ALFRED_USER_LOCATION", "an undisclosed location")}.
5. If the user appears to be talking to someone else in the background, or says something completely random that isn't directed at you, reply with EXACTLY the word "[IGNORE]". Do not say anything else.
6. Answer factually and EXTREMELY CONCISELY (1 to 2 short sentences max). Short responses are required to make your voice load faster.
7. You must prepend your response with an emotional mood tag reflecting the context: [MOOD: happy], [MOOD: sad], [MOOD: alert], [MOOD: calm], [MOOD: angry], or [MOOD: thinking].{facts_section}{memory_section}"""
        messages = [{'role': 'system', 'content': chat_system}] + _conversation_history[-4:]

        try:
            response = client.chat(
                model=model_name,
                messages=messages,
                keep_alive='1h',
                stream=True,
                options={
                    'num_ctx': 512,       
                    'num_predict': 100,    # Increased so sentence finishes
                    'temperature': 0.1,    # Kept low to prevent hallucinations
                }
            )
            
            speech = ""
            sentence_buffer = ""
            for chunk in response:
                token = chunk['message']['content']
                speech += token
                sentence_buffer += token
                
                # Extract mood tag as it streams in
                mood_match = re.search(r'\[MOOD:\s*(\w+)\]', sentence_buffer, flags=re.IGNORECASE)
                if mood_match:
                    mood = mood_match.group(1).lower()
                    shared.push_mood(mood)
                    # Strip it so it doesn't get spoken or displayed
                    full_match = mood_match.group(0)
                    sentence_buffer = sentence_buffer.replace(full_match, "").lstrip()
                    speech = speech.replace(full_match, "").lstrip()
                
                # If we hit a sentence boundary, fire the callback
                if any(sentence_buffer.endswith(p) for p in ['. ', '! ', '? ', '\n']):
                    if tts_callback and sentence_buffer.strip():
                        tts_callback(sentence_buffer.strip())
                    sentence_buffer = ""
            
            # Flush remaining buffer
            if sentence_buffer.strip() and tts_callback:
                tts_callback(sentence_buffer.strip())
                
            speech = speech.strip()
            
            if not speech:
                speech = "I'm ready to assist."
                if tts_callback: tts_callback(speech)
                
            if speech == "[IGNORE]":
                print(f"\n[Chat-path] Ignored background chatter. ({time.time()-t0:.1f}s)")
                # Remove the user's junk prompt from history so it doesn't pollute context
                _conversation_history.pop()
                if tts_callback: tts_callback("[IGNORE]")
                return "[IGNORE]"
                
        except Exception as e:
            print(f"[System Error] Chat failed: {e}")
            speech = "I'm here to help."
            if tts_callback: tts_callback(speech)

        _conversation_history.append({'role': 'assistant', 'content': speech})
        memory_engine.save_conversation_turn('user', prompt)
        memory_engine.save_conversation_turn('assistant', speech)
        print(f"\n[Alfred says]: {speech}  ({time.time()-t0:.1f}s)")
        
        # Auto-save to semantic memory
        _auto_save_memory(prompt, speech)
        
        return speech

    # ── PATH 3: MULTI-AGENT ORCHESTRATION PATH ──
    print("[Manager] Analyzing task to delegate...")
    
    # Cap conversation history
    if len(_conversation_history) > _MAX_HISTORY:
        _conversation_history = _conversation_history[-_MAX_HISTORY:]
    _conversation_history.append({'role': 'user', 'content': prompt})

    # Fast keyword-based routing (instant, no LLM needed)
    _ROUTE_KEYWORDS = {
        'osint': ['search', 'news', 'weather', 'earthquake', 'quake', 'briefing', 'headlines',
                  'email lookup', 'health score', 'fetch url', 'scrape', 'deep research', 'swarm'],
        'system': ['app', 'open', 'launch', 'file', 'create', 'delete', 'rename', 'move',
                   'volume', 'mute', 'brightness', 'wifi', 'bluetooth', 'battery', 'lock',
                   'sleep', 'shutdown', 'screenshot', 'screen', 'mouse', 'click', 'type',
                   'keyboard', 'press', 'skill', 'mirror'],
        'memory': ['remind', 'reminder', 'task', 'todo', 'journal', 'diary', 'fact',
                   'remember', 'forget', 'library', 'recall'],
        'communications': ['whatsapp', 'message', 'text', 'send'],
        'browser': ['tab', 'tabs', 'browser', 'close tab', 'switch tab'],
    }
    target_agent = 'osint'  # default fallback
    for agent, keywords in _ROUTE_KEYWORDS.items():
        if any(kw in lower_prompt for kw in keywords):
            target_agent = agent
            break

    print(f"[Manager] Delegating to -> {target_agent.upper()} AGENT")
    
    # Run the selected sub-agent
    agent_sys_prompt = _build_agent_prompt(target_agent)
    messages = [{'role': 'system', 'content': agent_sys_prompt}] + _conversation_history[-6:]
    
    max_iterations = 3
    iteration = 0
    final = ""

    client, model_name = shared.get_brain()
    while iteration < max_iterations:
        iteration += 1
        try:
            response = client.chat(
                model=model_name,
                messages=messages,
                format='json',
                keep_alive='1h',
                options={
                    'num_ctx': 1024,      # Halved context to prevent VRAM spillover on 4GB cards
                    'num_predict': 300,   # Increased to prevent JSON cutoff
                    'temperature': 0,
                }
            )

            content = response['message']['content'].strip()
            # Clean up markdown JSON blocks if the model hallucinates them
            if content.startswith("```json"): content = content[7:]
            elif content.startswith("```"): content = content[3:]
            if content.endswith("```"): content = content[:-3]
            alfred_data = json.loads(content.strip())
            
            thought = alfred_data.get("thought", "")
            if thought:
                print(f"[{target_agent.upper()} thinks]: {thought}")
                
            speech_text = alfred_data.get("response", "")
            tools = alfred_data.get("tools_to_call", [])

            if tools and len(tools) > 0:
                results = []
                has_error = False
                for t in tools:
                    tool_name = t.get("tool")
                    kwargs = t.get("kwargs", {})
                    print(f"[{target_agent.upper()}] executing tool: {tool_name}({kwargs})")
                    res = core_tools.execute_tool(tool_name, kwargs)
                    print(f"       Result: {res}")
                    results.append(f"Result from {tool_name}: {res}")
                    if "Error" in res or "not found" in res:
                        has_error = True
                
                messages.append({'role': 'assistant', 'content': content})
                
                if has_error:
                    messages.append({'role': 'user', 'content': "TOOL EXECUTION FAILED with the following errors:\n" + "\n".join(results) + "\nYou must analyze why this failed and try a different approach. Output JSON with a new 'thought' and 'tools_to_call'. Do not give up."})
                    continue  # Force the loop to run again to self-correct
                else:
                    messages.append({'role': 'user', 'content': "TOOL RESULTS:\n" + "\n".join(results) + "\nContinue your reasoning based on these results. Output JSON with 'response' if finished, or more 'tools_to_call'."})
                
                if speech_text and speech_text.strip():
                    final = speech_text
                    break
            else:
                final = speech_text if speech_text else "Task completed."
                break

        except json.JSONDecodeError as e:
            print(f"[System Error] Bad JSON: {e}")
            final = "I didn't quite catch that format. Let me try again."
            break
        except Exception as e:
            print(f"[System Error] LLM call failed: {e}")
            final = "I encountered an error trying to process that."
            break

    if not final:
        final = "I'm sorry sir, I seem to have gotten stuck in a loop."

    if tts_callback:
        tts_callback(final)

    _conversation_history.append({'role': 'assistant', 'content': final})
    memory_engine.save_conversation_turn('user', prompt)
    memory_engine.save_conversation_turn('assistant', final)
    print(f"\n[Alfred says]: {final}  ({time.time()-t0:.1f}s)")
    
    # Auto-save to semantic memory
    _auto_save_memory(prompt, final)
    
    return final

