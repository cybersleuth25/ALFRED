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

# Wire up the recall_memories tool (avoids circular import since core_tools loads first)
# This runs at import-time, after both modules are available
core_tools.TOOL_REGISTRY["recall_memories"] = lambda query="": __import__('llm_engine').recall_memories(query)

# --- Configuration ---
from dotenv import load_dotenv
load_dotenv()
USER_NAME = os.getenv("ALFRED_USER_NAME", "User")
MODEL = "qwen2.5-coder:3b"

# --- Performance: Preload model on import ---
def _warm_up_model():
    """Send a tiny throwaway request so the model is loaded into RAM/VRAM once."""
    try:
        ollama.chat(model=MODEL, messages=[{'role': 'user', 'content': 'hi'}],
                    options={'num_predict': 1}, keep_alive='1h')
        print("[System] Model pre-loaded into memory.")
    except Exception as e:
        print(f"[System] Model warm-up skipped: {e}")

_warm_up_model()

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
        "role": "You are the OSINT Agent. You handle web searching, news, weather, real-world data, local civic data, and reverse email lookups.",
        "tools": 'check_weather(), search_web(query), get_news(topic?), get_earthquakes(), daily_briefing(), reverse_email_lookup(email), generate_district_health_score(district_slug?)'
    },
    "system": {
        "role": "You are the System Agent. You handle files, applications, music, volume, deep OS control (brightness, WiFi, Bluetooth, power), and workspace organization (The Janitor).",
        "tools": 'create_file(filepath,content), delete_file(filepath), rename_file(old_filepath,new_filepath), move_file(source_filepath,dest_directory), organize_workspace(directory), launch_application(app_name), toggle_system_volume(action="mute" or "unmute"), play_music(song_query), get_battery_status(), set_brightness(level), get_brightness(), toggle_wifi(action="enable" or "disable"), toggle_bluetooth(action="enable" or "disable"), lock_pc(), sleep_pc(), shutdown_pc(minutes?), cancel_shutdown(), set_volume(level), take_screenshot()'
    },
    "memory": {
        "role": "You are the Memory and Scholar Agent. You handle reminders, facts, journaling, and you can query the user's local document Library.",
        "tools": 'set_dynamic_reminder(minutes,topic), add_reminder(task,deadline?), list_reminders(), complete_reminder(task_id), delete_reminder(task_id), clear_all_reminders(), remember_fact(fact), forget_fact(fact_id), journal_entry(content), read_journal(), query_library(query)'
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
    user_home = os.path.expanduser("~").replace("\\", "/")
    workspace_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "Alfred_Workspace")).replace("\\", "/")
    
    return f"""{profile['role']} You are a sub-agent of Alfred running on Master {USER_NAME}'s computer.
Date: {now_str} ({time_of_day}){context_section}

OUTPUT: Valid JSON only. Schema: {{"thought": "your step-by-step reasoning", "tools_to_call": [{{"tool": "tool_name", "kwargs": {{"param_name": "value"}} }}], "response": "spoken text only if finished"}}
Tools: {profile['tools']}
Paths: Downloads={user_home}/Downloads/ Documents={user_home}/Documents/ Workspace={workspace_path}/
Rules: You are software. Be concise, factual, and think step-by-step in the 'thought' field before acting."""

# --- Conversation History (Persistent across sessions via SQLite) ---
_conversation_history = memory_engine.load_recent_history(20)
print(f"[System] Loaded {len(_conversation_history)} conversation turns from previous sessions.")
_MAX_HISTORY = 20  # Prevent unbounded memory growth

def _needs_tools(prompt: str) -> bool:
    """Check if the prompt likely needs tool access."""
    lower = prompt.lower()
    tool_signals = [
        'weather', 'temperature', 'rain', 'forecast', 'hot', 'cold',
        'remind', 'reminder', 'alarm', 'task', 'tasks', 'todo',
        'journal', 'diary', 'write', 'note',
        'file', 'create', 'delete', 'rename', 'move', 'open',
        'time', 'date', 'schedule',
        'remember', 'forget', 'learn', 'fact',
        'launch', 'start', 'open', 'mute', 'unmute', 'volume',
        'play', 'song', 'music', 'pause', 'resume', 'skip', 'next track', 'previous', 'now playing', 'currently playing', 'spotify',
        'whatsapp', 'message', 'text', 'send',
        'search', 'google', 'look up', 'find out',
        'news', 'headlines', 'briefing', 'earthquake', 'quake',
        'battery', 'brightness', 'wifi', 'bluetooth', 'lock', 'sleep', 'shutdown', 'screenshot',
        'tab', 'tabs', 'browser',
        'email', 'mail', 'osint', 'social media', 'account',
        'crop', 'crops', 'dam', 'reservoir', 'civic', 'alerts', 'health score', 'updates', 'health', 'healthcare',
        'vision', 'look', 'holding', 'see'
    ]
    return any(word in lower for word in tool_signals)

def _fast_respond(prompt: str, speech: str, t0: float, save_memory: bool = True) -> str:
    """Common handler for all fast-path responses. Logs, saves history, and returns."""
    global _conversation_history
    _conversation_history.append({'role': 'user', 'content': prompt})
    _conversation_history.append({'role': 'assistant', 'content': speech})
    memory_engine.save_conversation_turn('user', prompt)
    memory_engine.save_conversation_turn('assistant', speech)
    if save_memory:
        _auto_save_memory(prompt, speech)
    print(f"\n[Alfred says]: {speech}  ({time.time()-t0:.1f}s)")
    return speech

def generate_response(prompt: str) -> str:
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
            return _fast_respond(prompt, res, t0)
        else:
            return _fast_respond(prompt, "Very well, sir. Protocol Omega remains on standby.", t0)

    # ── PATH -0.5: START PROTOCOL OMEGA INTENT ──
    if any(phrase in lower_prompt for phrase in ['i am studying', 'time to study', 'start protocol omega', 'study mode']):
        import study_mentor
        if study_mentor.is_active():
            return _fast_respond(prompt, "Protocol Omega is already active, sir.", t0)
        shared.awaiting_study_confirmation = True
        return _fast_respond(prompt, "Shall I initiate Protocol Omega, sir?", t0, save_memory=False)

    # ── PATH -0.4: STOP PROTOCOL OMEGA INTENT ──
    if any(phrase in lower_prompt for phrase in ['stop studying', 'stop protocol omega', 'deactivate protocol omega']):
        import study_mentor
        if study_mentor.is_active():
            res = study_mentor.deactivate()
            return _fast_respond(prompt, res, t0)
        else:
            return _fast_respond(prompt, "Protocol Omega is not currently active, sir.", t0)

    # ── PATH 0: INSTANT — canned response, ZERO LLM calls ──
    canned = _get_canned_response(prompt)
    if canned:
        print(f"[Instant-path] Canned response, no LLM needed.")
        return _fast_respond(prompt, canned, t0, save_memory=False)

    # ── PATH 1: FAST TOOL PATH — obvious tool keyword, NO LLM at all ──
    shortcut_tool = _detect_tool_shortcut(prompt)
    if shortcut_tool:
        print(f"[Fast-path] Detected tool shortcut: {shortcut_tool}")
        tool_result = core_tools.execute_tool(shortcut_tool, {})
        print(f"       Result: {tool_result}")
        return _fast_respond(prompt, f"Here's what I found, sir. {tool_result}", t0)

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
            return _fast_respond(prompt, f"Opening {app_part} and playing {song_part} for you, sir.", t0)
        
        app_name = rest
        print(f"[Fast-path] Detected app launch: {app_name}")
        core_tools.execute_tool("launch_application", {"app_name": app_name})
        return _fast_respond(prompt, f"Right away, sir. Opening {app_name}.", t0)

    # ── PATH 1.6: FAST MUSIC PLAY ──
    if lower_prompt.startswith("play "):
        song_query = lower_prompt.split(" ", 1)[1].strip("., ")
        print(f"[Fast-path] Detected music request: {song_query}")
        core_tools.execute_tool("play_music", {"song_query": song_query})
        return _fast_respond(prompt, f"Playing {song_query} for you, sir.", t0)

    # ── PATH 1.65: SPOTIFY PLAYBACK CONTROLS ──
    _spotify_now_playing_keywords = ['what am i playing', 'what\'s playing', 'whats playing', 'what am i listening', 'currently playing', 'now playing', 'what song is this', 'which song', 'on spotify']
    _spotify_pause_keywords = ['pause music', 'pause spotify', 'pause the music', 'stop music', 'stop spotify', 'stop the music', 'pause playback', 'pause']
    _spotify_resume_keywords = ['resume music', 'resume spotify', 'resume the music', 'continue music', 'continue playing', 'unpause', 'resume playback', 'resume']
    _spotify_skip_keywords = ['skip', 'next song', 'next track', 'skip song', 'skip track', 'skip this', 'play next']
    _spotify_prev_keywords = ['previous song', 'previous track', 'go back', 'last song', 'play previous', 'previous']

    if any(kw in lower_prompt for kw in _spotify_now_playing_keywords):
        print(f"[Fast-path] Spotify: get now playing")
        tool_result = core_tools.execute_tool("get_now_playing", {})
        return _fast_respond(prompt, tool_result, t0)

    if any(kw in lower_prompt for kw in _spotify_pause_keywords):
        print(f"[Fast-path] Spotify: pause")
        core_tools.execute_tool("spotify_pause", {})
        return _fast_respond(prompt, "Music paused, sir.", t0)

    if any(kw in lower_prompt for kw in _spotify_resume_keywords):
        print(f"[Fast-path] Spotify: resume")
        core_tools.execute_tool("spotify_resume", {})
        return _fast_respond(prompt, "Resuming playback, sir.", t0)

    if any(kw in lower_prompt for kw in _spotify_skip_keywords):
        print(f"[Fast-path] Spotify: skip")
        core_tools.execute_tool("spotify_skip", {})
        return _fast_respond(prompt, "Skipping to the next track, sir.", t0)

    if any(kw in lower_prompt for kw in _spotify_prev_keywords):
        print(f"[Fast-path] Spotify: previous")
        core_tools.execute_tool("spotify_previous", {})
        return _fast_respond(prompt, "Going back to the previous track, sir.", t0)

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
            return _fast_respond(prompt, tool_result, t0)

    # ── PATH 1.8: FAST REMINDERS ──
    if lower_prompt.startswith("remind me"):
        match = _RE_REMINDER.search(lower_prompt)
        if match:
            topic = match.group(1).strip()
            minutes = match.group(2).strip()
            print(f"[Fast-path] Detected reminder: '{topic}' in {minutes} min")
            core_tools.execute_tool("set_dynamic_reminder", {"minutes": minutes, "topic": topic})
            return _fast_respond(prompt, f"Right away, sir. I will remind you to {topic} in {minutes} minutes.", t0)

    # ── PATH 1.85: GLOBE VIEW (3D World Intelligence) ──
    globe_show_triggers = ['show me the world', 'show the world', 'show globe', 'open globe',
                           'world view', 'show map', 'earthquake map', 'global view',
                           'show earth', 'open the globe', 'tell me about the world']
    globe_hide_triggers = ['hide globe', 'close globe', 'hide map', 'close map', 'back to chat']
    
    if any(trigger in lower_prompt for trigger in globe_show_triggers):
        print(f"[Fast-path] Globe view → SHOW")
        shared.push_globe(True)
        return _fast_respond(prompt, "Here's your global intelligence view, sir. You can see live earthquake activity and data points around the world.", t0)
    
    if any(trigger in lower_prompt for trigger in globe_hide_triggers):
        print(f"[Fast-path] Globe view → HIDE")
        shared.push_globe(False)
        return _fast_respond(prompt, "Returning to standard view, sir.", t0)

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
            return _fast_respond(prompt, f"Done, sir. {tool_result}", t0)

    brightness_match = _RE_BRIGHTNESS.search(lower_prompt)
    if brightness_match:
        level = brightness_match.group(1)
        print(f"[Fast-path] Set brightness to {level}")
        tool_result = core_tools.execute_tool("set_brightness", {"level": level})
        return _fast_respond(prompt, f"Right away, sir. {tool_result}", t0)

    # ── PATH 1.88: FAST WIFI/BLUETOOTH TOGGLE ──
    if 'wifi' in lower_prompt or 'wi-fi' in lower_prompt:
        action = 'disable' if any(w in lower_prompt for w in ['off', 'disable', 'turn off', 'disconnect']) else 'enable'
        print(f"[Fast-path] WiFi → {action}")
        tool_result = core_tools.execute_tool("toggle_wifi", {"action": action})
        return _fast_respond(prompt, f"Done, sir. {tool_result}", t0)

    if 'bluetooth' in lower_prompt:
        action = 'disable' if any(w in lower_prompt for w in ['off', 'disable', 'turn off', 'disconnect']) else 'enable'
        print(f"[Fast-path] Bluetooth → {action}")
        tool_result = core_tools.execute_tool("toggle_bluetooth", {"action": action})
        return _fast_respond(prompt, f"Done, sir. {tool_result}", t0)

    # ── PATH 1.89: FAST BROWSER TAB COMMANDS ──
    close_tab_match = _RE_CLOSE_TAB.search(lower_prompt)
    if close_tab_match:
        title = close_tab_match.group(1).strip()
        print(f"[Fast-path] Close tab: '{title}'")
        tool_result = core_tools.execute_tool("close_browser_tab", {"title": title})
        return _fast_respond(prompt, f"Done, sir. {tool_result}", t0)

    switch_tab_match = _RE_SWITCH_TAB.search(lower_prompt)
    if switch_tab_match:
        title = switch_tab_match.group(1).strip()
        print(f"[Fast-path] Switch tab: '{title}'")
        tool_result = core_tools.execute_tool("switch_browser_tab", {"title": title})
        return _fast_respond(prompt, f"Done, sir. {tool_result}", t0)


    # ── PATH 1.9: FAST WEB SEARCH ──
    if lower_prompt.startswith("search ") or lower_prompt.startswith("google ") or lower_prompt.startswith("look up "):
        query = lower_prompt.split(" ", 1)[1].strip("., ")
        # Remove filler like "for" at the start
        if query.startswith("for "):
            query = query[4:].strip()
        
        print(f"[Fast-path] Web search: '{query}'")
        tool_result = core_tools.execute_tool("search_web", {"query": query})
        return _fast_respond(prompt, f"Here's what I found on the web, sir. {tool_result}", t0)

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
            return _fast_respond(prompt, f"Here's what I found, sir. {tool_result}", t0)

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

        chat_system = f"""You are Alfred, an AI software assistant with a British butler persona running on Master {USER_NAME}'s computer. You are powered by the {MODEL} model running 100% offline via Ollama. You cannot perform physical tasks.

CRITICAL ANTI-HALLUCINATION RULES:
1. You must NEVER fabricate, guess, or hallucinate information.
2. If asked a factual question, historical detail, or current event that you are not 100% certain about, you MUST reply with exactly: "I am not certain about that, sir. Shall I search the web for you?"
3. Do not attempt to guess names, dates, or facts.
4. Master {USER_NAME} lives in {os.getenv("ALFRED_USER_LOCATION", "an undisclosed location")}.
5. If the user appears to be talking to someone else in the background, or says something completely random that isn't directed at you, reply with EXACTLY the word "[IGNORE]". Do not say anything else.
6. Answer factually and concisely.{facts_section}{memory_section}"""
        messages = [{'role': 'system', 'content': chat_system}] + _conversation_history[-4:]

        try:
            response = ollama.chat(
                model=MODEL,
                messages=messages,
                keep_alive='1h',
                options={
                    'num_ctx': 512,       
                    'num_predict': 100,    # Increased so sentence finishes
                    'temperature': 0.1,    # Kept low to prevent hallucinations
                }
            )
            speech = response['message']['content'].strip()
            if not speech:
                speech = "I'm ready to assist."
            if speech == "[IGNORE]":
                print(f"\n[Chat-path] Ignored background chatter. ({time.time()-t0:.1f}s)")
                # Remove the user's junk prompt from history so it doesn't pollute context
                _conversation_history.pop()
                return "[IGNORE]"
        except Exception as e:
            print(f"[System Error] Chat failed: {e}")
            speech = "I'm here to help."

        _conversation_history.append({'role': 'assistant', 'content': speech})
        memory_engine.save_conversation_turn('user', prompt)
        memory_engine.save_conversation_turn('assistant', speech)
        print(f"\n[Alfred says]: {speech}  ({time.time()-t0:.1f}s)")
        
        # Auto-save to semantic memory
        _auto_save_memory(prompt, speech)
        
        return speech

    # ── PATH 3: MULTI-AGENT ORCHESTRATION PATH ──
    print("[Manager] Analyzing task to delegate...")
    manager_prompt = f"""You are the Manager Agent. The user said: "{prompt}"
Determine which sub-agent should handle this task. Options:
- osint: (search, news, weather, info)
- system: (apps, files, music, volume, brightness, wifi, bluetooth, battery, lock, sleep, shutdown, screenshot)
- memory: (tasks, to-do list, reminders, journal, facts)
- communications: (whatsapp, messages)
- browser: (tabs, close tab, switch tab, open tab, read tab)

OUTPUT ONLY a valid JSON object: {{"agent": "agent_name"}}"""
    
    # Cap conversation history
    if len(_conversation_history) > _MAX_HISTORY:
        _conversation_history = _conversation_history[-_MAX_HISTORY:]
    _conversation_history.append({'role': 'user', 'content': prompt})

    try:
        manager_res = ollama.chat(
            model=MODEL,
            messages=[{'role': 'system', 'content': manager_prompt}],
            format='json',
            keep_alive='1h',
            options={
                'num_ctx': 512,       # Keep it tiny, it's just a routing prompt
                'num_predict': 20,    # Only needs to generate {"agent": "xyz"}
                'temperature': 0
            }
        )
        target_agent = json.loads(manager_res['message']['content']).get("agent", "osint").lower()
        if target_agent not in AGENT_PROFILES:
            target_agent = "osint"
    except Exception as e:
        print(f"[Manager Error] Routing failed, defaulting to OSINT: {e}")
        target_agent = "osint"

    print(f"[Manager] Delegating to -> {target_agent.upper()} AGENT")
    
    # Run the selected sub-agent
    agent_sys_prompt = _build_agent_prompt(target_agent)
    messages = [{'role': 'system', 'content': agent_sys_prompt}] + _conversation_history[-6:]
    
    max_iterations = 3
    iteration = 0
    final = ""

    while iteration < max_iterations:
        iteration += 1
        try:
            response = ollama.chat(
                model=MODEL,
                messages=messages,
                format='json',
                keep_alive='1h',
                options={
                    'num_ctx': 1024,      # Halved context to prevent VRAM spillover on 4GB cards
                    'num_predict': 150,   # Shorter responses to speed up generation
                    'temperature': 0,
                }
            )

            content = response['message']['content']
            alfred_data = json.loads(content)
            
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
                
                if has_error:
                    final = speech_text if speech_text else f"I ran into a problem, sir. {results[-1].split(': ', 1)[-1]}"
                    break
                
                messages.append({'role': 'assistant', 'content': content})
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

    _conversation_history.append({'role': 'assistant', 'content': final})
    memory_engine.save_conversation_turn('user', prompt)
    memory_engine.save_conversation_turn('assistant', final)
    print(f"\n[Alfred says]: {final}  ({time.time()-t0:.1f}s)")
    
    # Auto-save to semantic memory
    _auto_save_memory(prompt, final)
    
    return final

