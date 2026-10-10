import threading
import json
import os
import sys
import re
import time
import random
from datetime import datetime

# Add the root directory to path to ensure we can import tools & memory_engine normally
sys.path.append(os.path.dirname(__file__))

# Ensure UTF-8 console output on Windows to support Devanagari Hindi characters without crashing
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from tools import core_tools
import memory_engine
import shared
import persona_engine
import commands

# ── Pre-compiled Regex Patterns (compiled once at module load) ──
_RE_BRIGHTNESS = re.compile(r'(?:set |change )?brightness (?:to |at )?(\d+)')
_RE_CLOSE_TAB = re.compile(r'close (?:the )?(.+?) tab')
_RE_SWITCH_TAB = re.compile(r'switch to (?:the )?(.+?) tab')
_RE_WHATSAPP = re.compile(r'(?:whatsapp|message)\s+(?:to\s+)?(?:my\s+)?(.+?)\s+(?:saying|that|say)\s+(.+)', re.IGNORECASE)
_RE_WHATSAPP_SIMPLE = re.compile(r'(?:whatsapp|message)\s+(?:to\s+)?(?:my\s+)?(\w+)\s+(.+)', re.IGNORECASE)
_RE_REMINDER = re.compile(r'remind me (?:to|about)?\s+(.+)\s+in\s+(\d+)\s+min', re.IGNORECASE)
_RE_KNOWLEDGE = re.compile(r'^(who|what|where|when|why|how|which|tell me|explain|describe)\b\s+(.+)', re.IGNORECASE)
_RE_INSTAGRAM = re.compile(r'(?:check|read|fetch|scrape) instagram (?:for )?(?:what )?(?:is on )?(?:@)?(\w+)', re.IGNORECASE)

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
    'time', 'date', 'schedule', 'calendar', 'meeting', 'meetings', 'event', 'events', 'agenda', 'appointment',
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
    'search', 'google', 'look up', 'find out', 'deep dive', 'deep research', 'swarm', 'research', 'dossier', 'investigate',
    # News & OSINT
    'news', 'headlines', 'briefing', 'earthquake', 'quake',
    'world', 'global', 'happening',
    'email', 'mail', 'osint', 'social media', 'account', 'instagram', 'insta',
    # Market & Stock Intelligence (Amazon Chronos)
    'stock', 'stocks', 'share', 'shares', 'equity', 'equities', 'nifty', 'sensex', 'ticker',
    'market', 'quote', 'chronos', 'prediction',
    # Facial OSINT & Reverse Face Search
    'face', 'facesearch', 'pimeyes', 'faceseek', 'chehra',
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
    # Scholar & Library
    'library', 'scholar', 'textbook', 'pdf', 'papers', 'research paper', 'study notes',
])

# Wire up the recall_memories tool (avoids circular import since core_tools loads first)
# This runs at import-time, after both modules are available
core_tools.TOOL_REGISTRY["recall_memories"] = lambda query="": __import__('llm_engine').recall_memories(query)

# --- Configuration ---
from dotenv import load_dotenv
load_dotenv()
USER_NAME = os.getenv("ALFRED_USER_NAME", "User")

# --- Brain Access ---
def chat(messages, options=None, format=None, smart=False):
    """Unified chat function for external modules to use the active brain."""
    client, model_name = shared.get_brain(smart=smart)
    try:
        kwargs = {
            "model": model_name,
            "messages": messages,
        }
        if format == 'json':
            kwargs["response_format"] = {"type": "json_object"}
        if options and 'temperature' in options:
            kwargs["temperature"] = options['temperature']
            
        res = client.chat.completions.create(**kwargs)
        
        # Return an ollama-compatible dictionary so we don't break external callers
        return {
            'message': {
                'content': res.choices[0].message.content
            }
        }
    except Exception as e:
        print(f"[LLM] Chat failed: {e}")
        raise e


# --- Instant canned responses (NO LLM call, 0 seconds) ---
_GREETINGS = {
    'hello': ["Hey there, {name}! What's up?", "Hello! Good to hear from you, sir. What do you need?", "Hey, {name}! I'm here. What can I do for you?"],
    'hi': ["Hey! What's on your mind, sir?", "Hi, {name}! I'm all ears.", "Hey there! What do you need?"],
    'hey': ["Hey hey! What can I help with, sir?", "Hey, {name}! Ready when you are.", "What's up? I'm listening."],
    'how are you': ["I'm doing great, {name}! Better now that you're here. How about you?", "Honestly? Pretty good, sir. Always happy when we're working together. How are you?", "Can't complain! Well, technically I can, but I won't. How are you doing, {name}?"],
    'good morning': ["Morning, {name}! Hope you slept well. What are we doing today?", "Good morning! I love a fresh start, sir. What's the plan?", "Morning! Ready to make today awesome, {name}?"],
    'good evening': ["Evening, {name}! How was your day?", "Good evening, sir! Nice to see you. What do you need?", "Hey, good evening! Hope the day treated you well, {name}."],
    'good night': ["Night, {name}! Get some rest, you've earned it.", "Good night, sir. I'll keep an eye on things while you sleep.", "Sweet dreams, {name}! I'll be right here when you wake up."],
    'thank you': ["Anytime, {name}! That's what I'm here for.", "You're welcome, sir! Happy to help.", "Of course! Don't even mention it, {name}.", "Always, sir. It's genuinely my pleasure."],
    'thanks': ["No problem at all, {name}!", "You got it, sir!", "Anytime! That's what friends are for.", "Happy to help, {name}!"],
    'what can you do': ["Oh, where do I even start? Weather, reminders, music, file management, web search, journaling, taking screenshots, controlling your desktop, deep research, and honestly just being a great conversationalist, sir.", "A lot, actually! Think of me as your personal assistant who never sleeps and never complains, {name}. Weather, reminders, music, research, you name it."],
    'who are you': ["I'm Alfred! Your AI companion, sir. Part butler, part best friend, fully dedicated to making your life easier.", "I'm Alfred, {name}. Think of me as the friend who's always available, always helpful, and never borrows money."],
    # Hindi & Indian English greetings
    'namaste': ["Namaste {name}! Kaise hain aap? Main aapki kya madad kar sakta hoon?", "Namaste sir! Good to hear from you. What can I do for you today?"],
    'kaise ho': ["Main bilkul theek hoon {name}! Aap bataiye, aaj kya chal raha hai?", "Sab badiya sir! Aapki seva mein hazir hoon."],
    'kya haal hai': ["Sab mast hai {name}! Aap bataiye, kya madad chahiye?"],
    'shukriya': ["Arey koi baat nahi {name}! Hamesha aapki seva mein.", "You are most welcome, sir!"],
    'dhanyawad': ["Aapka swagat hai {name}! Kabhi bhi kuch bhi chahiye ho, toh batayiye."],
}

def _get_canned_response(prompt: str):
    """Return instant response for common phrases, or None."""
    lower = prompt.lower().strip().rstrip('?!.,')
    words = lower.split()
    
    # If the user is asking a longer question/command, don't interrupt it with a canned greeting.
    if len(words) > 4:
        return None
        
    for key, responses in _GREETINGS.items():
        if lower == key or (lower.startswith(f"{key} ") and len(words) <= 3) or key in words and len(words) <= 3:
            resp = random.choice(responses)
            import persona_engine
            persona = persona_engine.get_active_persona()
            # Dynamically adapt the response to the persona's title, honorific, and display name
            resp = resp.replace("Master {name}", persona.get_title(USER_NAME))
            if "sir" in resp and persona.honorific != "sir":
                resp = resp.replace("sir", persona.honorific)
            resp = resp.replace("Alfred", persona.display_name)
            return resp.format(name=USER_NAME)
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

        # Auto-extract entities and relationships into the Knowledge Graph (Second Brain)
        try:
            import knowledge_graph
            import threading
            threading.Thread(
                target=knowledge_graph.extract_and_link_from_text,
                args=(f"User: {user_msg}\nAlfred: {alfred_response}",),
                daemon=True,
                name="KG-Extractor"
            ).start()
        except Exception:
            pass
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

def get_status_report() -> str:
    """Compiles a comprehensive butler status briefing of the user's workspace, tasks, and system."""
    import psutil
    persona = persona_engine.get_active_persona()
    title = persona.get_title(USER_NAME)
    
    parts = []
    
    # 1. Pending Tasks / Reminders
    try:
        pending = memory_engine.get_pending_tasks()
        if pending:
            task_count = len(pending)
            first_tasks = [t['task'] for t in pending[:3]]
            tasks_str = ", ".join(f"'{t}'" for t in first_tasks)
            if task_count > 3:
                parts.append(f"You have {task_count} pending tasks, including {tasks_str} and {task_count - 3} more")
            else:
                parts.append(f"You have {task_count} pending task{'s' if task_count > 1 else ''}: {tasks_str}")
        else:
            parts.append("Your task list is completely clear")
    except Exception:
        pass

    # 1b. Google & Samsung Calendar Schedule
    try:
        from tools import calendar_tools
        cal_summary = calendar_tools.get_today_events_summary()
        if cal_summary and "no scheduled" not in cal_summary.lower():
            parts.append(cal_summary)
    except Exception:
        pass

    # 2. Focus / Study Protocol
    if getattr(shared, 'omega_active', False):
        mins_left = getattr(shared, 'omega_phase_remaining', 0) // 60
        parts.append(f"Focus Mode is active in {getattr(shared, 'omega_phase', 'focus')} phase with {mins_left} minutes remaining")
    
    # 3. System Health
    try:
        battery = psutil.sensors_battery()
        if battery:
            plugged_str = "plugged in" if battery.power_plugged else "on battery"
            parts.append(f"battery is at {battery.percent}% ({plugged_str})")
        cpu = psutil.cpu_percent()
        if cpu and cpu > 80:
            parts.append(f"CPU load is elevated at {cpu}%")
    except Exception:
        pass
        
    # 4. Spotify
    try:
        sp = core_tools.get_now_playing()
        if sp and all(x not in sp.lower() for x in ["nothing is currently playing", "not playing", "error", "no active"]):
            clean_sp = sp.replace("Currently playing: ", "").replace("Now playing: ", "").replace("Playing: ", "").strip()
            parts.append(f"music playing is {clean_sp}")
    except Exception:
        pass
        
    # 5. Sentry
    if getattr(shared, 'sentry_active', False):
        parts.append(f"Sentry vision is active (threat level: {getattr(shared, 'threat_level', 'none')})")

    status_body = ". ".join(parts) if parts else "All systems operating normally"
    return f"Here is your status report, {title}. {status_body}. All systems are optimal."

# --- Tool keywords for fast-path detection ---
_TOOL_KEYWORDS = {
    'weather': 'check_weather', 'temperature': 'check_weather', 'rain': 'check_weather',
    'hot': 'check_weather', 'cold': 'check_weather', 'weather forecast': 'check_weather',
    'journal': 'read_journal', 'diary': 'read_journal',
    'earthquake': 'get_earthquakes', 'earthquakes': 'get_earthquakes', 'quake': 'get_earthquakes', 'seismic': 'get_earthquakes',
    'briefing': 'daily_briefing', 'brief me': 'daily_briefing', 'intelligence': 'daily_briefing',
    'news': 'get_news', 'headlines': 'get_news', 'brief': 'daily_briefing',
    'with the world': 'get_news', 'in the world': 'get_news', 'around the world': 'get_news',
    'world news': 'get_news', 'world updates': 'get_news', 'current events': 'get_news',
    'global news': 'get_news', 'whats happening': 'get_news', "what's happening": 'get_news',
    'whats going on': 'get_news', "what's going on": 'get_news',
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
    # Market, financial, and face-search queries take precedence over generic keywords
    if any(k in lower for k in ['stock', 'share', 'market', 'ticker', 'nifty', 'sensex', 'chronos', 'face search', 'facesearch', 'reverse face']):
        return None
    for keyword, tool_name in _TOOL_KEYWORDS.items():
        if keyword in lower:
            return tool_name
    return None

def prewarm_model():
    """Background pre-warming task run at boot to eliminate first-call cold-start latencies."""
    try:
        # Pre-warm semantic memory embedding model
        memory_engine.search_memories("warmup", top_k=1)
    except Exception:
        pass
    try:
        # Pre-warm LLM brain connection
        client, model_name = shared.get_brain()
        client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=1
        )
    except Exception:
        pass

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
        "role": "You are the OSINT & Financial Intelligence Agent. You handle web searching, stock quotes, Amazon Chronos financial market forecasts (Indian equities NSE/BSE and US equities), reverse face search OSINT, news, weather, real-world data, and Multi-Agent deep swarm research.",
        "tools": 'check_weather(), search_web(query), get_stock_quote(symbol), forecast_stock(symbol, days?), reverse_face_search(image_path?), get_news(topic?), get_earthquakes(), daily_briefing(), reverse_email_lookup(email), generate_district_health_score(district_slug?), stealth_fetch_url(url), deep_research_swarm(topic)'
    },
    "system": {
        "role": "You are the System & Developer Agent. You have full physical control over the desktop (mouse/keyboard), you CAN see the screen using analyze_screen, and you can inspect git, scan secret leaks, clean workspaces, run terminal commands, and record meeting minutes. YOU MUST USE YOUR TOOLS.",
        "tools": 'create_file(filepath,content), delete_file(filepath), rename_file(old,new), move_file(src,dest), organize_workspace(dir), launch_application(app), toggle_system_volume(action), play_music(song), get_battery_status(), set_brightness(level), toggle_wifi(action), toggle_bluetooth(action), lock_pc(), sleep_pc(), shutdown_pc(), set_volume(level), take_screenshot(), analyze_screen(query), get_screen_info(), mouse_move_and_click(x,y,button,double_click), keyboard_type(text,press_enter), keyboard_press(key), keyboard_hotkey(key1,key2), learn_new_skill(skill), git_status_diff(repo_path?), git_smart_commit(commit_message?,repo_path?), scan_leaked_secrets(target_path?), clean_dev_workspace(root_dir?), run_terminal_command(command,cwd?), meeting_notetaker(action,title?)'
    },
    "memory": {
        "role": "You are the Memory and Scholar Agent. You handle reminders, calendar events (Google & Samsung Calendar), facts, journaling, Knowledge Graph relationships, and you can query the user's Photographic Screen Memory or local document Library.",
        "tools": 'set_dynamic_reminder(minutes,topic), add_reminder(task,deadline?), list_reminders(), complete_reminder(task_id), delete_reminder(task_id), clear_all_reminders(), get_calendar_events(days?), create_calendar_event(title,start_time,duration_minutes?,description?,location?), delete_calendar_event(query), remember_fact(fact), forget_fact(fact_id), journal_entry(content), read_journal(), query_library(query), recall_memories(query), query_knowledge_graph(entity_name)'
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

    # --- NEW: Inject contextual awareness (what the user is currently doing) ---
    try:
        import shared
        if shared.context_current_activity and shared.context_current_activity != "idle":
            import time as _time
            activity_duration = int((_time.time() - shared.context_activity_since) / 60) if shared.context_activity_since > 0 else 0
            context_section += f"\nCURRENT CONTEXT: User has been {shared.context_current_activity} for {activity_duration} minutes. Presence: {shared.context_presence}."
    except Exception:
        pass  # Non-critical

    # --- NEW: Inject Emotional Intelligence / Mood Adaptation ---
    try:
        import mood_engine
        mood_mod = mood_engine.get_mood_prompt_modifier()
        if mood_mod:
            context_section += f"\n{mood_mod}"
    except Exception:
        pass

    # --- NEW: Inject Knowledge Graph context if relevant ---
    try:
        if _conversation_history:
            last_text = _conversation_history[-1]["content"]
            import knowledge_graph
            kg_info = knowledge_graph.query_knowledge_summary(last_text)
            if kg_info:
                context_section += f"\n{kg_info}"
    except Exception:
        pass

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
    
    import persona_engine
    persona = persona_engine.get_active_persona()
    title = persona.get_title(USER_NAME)
    return f"""{profile['role']} You are a sub-agent of {persona.display_name} running on {title}'s computer.
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

def _safe_print(text: str):
    """Prints text safely on Windows terminals without crashing on unsupported Unicode characters."""
    try:
        print(text)
    except (UnicodeEncodeError, UnicodeDecodeError):
        try:
            print(text.encode('ascii', errors='replace').decode('ascii'))
        except Exception:
            pass

def _fast_respond(prompt: str, speech: str, t0: float, save_memory: bool = True, tts_callback=None) -> str:
    """Common handler for all fast-path responses. Logs, saves history, and returns."""
    global _conversation_history
    _conversation_history.append({'role': 'user', 'content': prompt})
    _conversation_history.append({'role': 'assistant', 'content': speech})
    memory_engine.save_conversation_turn('user', prompt)
    memory_engine.save_conversation_turn('assistant', speech)
    if save_memory:
        _auto_save_memory(prompt, speech)
    p = persona_engine.get_active_persona()
    _safe_print(f"\n[{p.display_name} says]: {speech}  ({time.time()-t0:.1f}s)")
    if tts_callback:
        tts_callback(speech)
    return speech

# Voice, HUD and Telegram threads all call generate_response; serialize them so
# _conversation_history and multi-step tool loops never interleave.
_response_lock = threading.RLock()


def generate_response(prompt: str, tts_callback=None) -> str:
    with _response_lock:
        t0 = time.time()
        confirmation_reply = core_tools.handle_confirmation_reply(prompt)
        if confirmation_reply is not None:
            return _fast_respond(prompt, str(confirmation_reply), t0, tts_callback=tts_callback)
        return _generate_response_unlocked(prompt, tts_callback)


def _generate_response_unlocked(prompt: str, tts_callback=None) -> str:
    global _conversation_history
    t0 = time.time()
    
    # Check for direct persona address (e.g. "Friday, what time is it?" or "Hey Jarvis, search the web")
    addressed_target, remaining_cmd = persona_engine.check_direct_address(prompt)
    if addressed_target:
        current_p = persona_engine.get_active_persona()
        if addressed_target != current_p.name:
            persona_engine.switch_persona(addressed_target)
        if not remaining_cmd.strip():
            p = persona_engine.get_active_persona()
            if addressed_target == 'friday':
                reply = f"Hey {p.honorific}, what's the plan?"
            elif addressed_target == 'jarvis':
                reply = f"At your service, {p.honorific}."
            else:
                reply = f"Alfred here, {p.get_title(USER_NAME)}."
            return _fast_respond(prompt, reply, t0, tts_callback=tts_callback)
        else:
            prompt = remaining_cmd

    p = persona_engine.get_active_persona()
    print(f"\n[{p.display_name} is thinking...]")
    
    lower_prompt = prompt.lower().strip()

    # ── PATH -1.5: CURRENT TIME ──
    if lower_prompt in {'what time is it', 'what is the time', 'tell me the time', 'current time'}:
        current_time = datetime.now().strftime('%I:%M %p').lstrip('0')
        return _fast_respond(prompt, f"It is currently {current_time}, sir.", t0, tts_callback=tts_callback)

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
    if any(phrase in lower_prompt for phrase in ['i am studying', 'time to study', 'start protocol omega', 'start focus mode', 'study mode']):
        import study_mentor
        if study_mentor.is_active():
            return _fast_respond(prompt, "Protocol Omega is already active, sir.", t0, tts_callback=tts_callback)
        shared.awaiting_study_confirmation = True
        return _fast_respond(prompt, "Shall I initiate Protocol Omega, sir?", t0, save_memory=False, tts_callback=tts_callback)

    # ── PATH -0.4: STOP PROTOCOL OMEGA INTENT ──
    if any(phrase in lower_prompt for phrase in ['stop studying', 'stop protocol omega', 'stop focus mode', 'deactivate protocol omega']):
        import study_mentor
        if study_mentor.is_active():
            res = study_mentor.deactivate()
            return _fast_respond(prompt, res, t0, tts_callback=tts_callback)
        else:
            return _fast_respond(prompt, "Protocol Omega is not currently active, sir.", t0, tts_callback=tts_callback)

    # ── PATH -0.3: WORKFLOW MACROS / ROUTINES EXECUTION ──
    try:
        import routine_engine
        matched_routine = routine_engine.match_voice_trigger(lower_prompt)
        if matched_routine:
            print(f"[Fast-path] Matched routine: {matched_routine['display_name']}")
            res = routine_engine.execute_routine(matched_routine["name"])
            return _fast_respond(prompt, res, t0, tts_callback=None)
    except Exception as e:
        print(f"[Routine Fast-Path Error] {e}")

    # ── PATH -0.2: CREATE ROUTINE FROM VOICE ──
    if any(lower_prompt.startswith(prefix) for prefix in ['create a routine', 'create routine', 'make a routine', 'new routine']):
        try:
            import routine_engine
            res = routine_engine.create_routine_from_prompt(prompt)
            if "error" in res:
                return _fast_respond(prompt, f"I had difficulty compiling that routine, sir: {res['error']}", t0, tts_callback=tts_callback)
            display = res.get("display_name", res.get("name", "Custom Routine"))
            return _fast_respond(prompt, f"Routine '{display}' has been created and saved, sir. You can trigger it anytime by saying its name.", t0, tts_callback=tts_callback)
        except Exception as e:
            return _fast_respond(prompt, f"Failed to create routine, sir: {e}", t0, tts_callback=tts_callback)


    # ── PATH -0.15: PERSONA SWITCHING ──
    target_p = persona_engine.extract_persona_name(lower_prompt)
    if target_p:
        persona_engine.switch_persona(target_p)
        p = persona_engine.get_active_persona()
        if target_p == 'friday':
            reply = f"F.R.I.D.A.Y. online and ready. What's the plan, {p.honorific}?"
        elif target_p == 'jarvis':
            reply = f"J.A.R.V.I.S. operational. At your service, {p.honorific}."
        else:
            reply = f"Alfred at your command, {p.get_title(USER_NAME)}."
        return _fast_respond(prompt, reply, t0, tts_callback=tts_callback)

    if any(m in lower_prompt for m in ["switch persona", "change persona", "switch voice", "change voice", "switch personality"]):
        p = persona_engine.get_active_persona()
        available = ", ".join(persona_engine.get_persona_names())
        reply = f"Which persona would you like, {p.honorific}? Available options are: {available}."
        return _fast_respond(prompt, reply, t0, tts_callback=tts_callback)

    # ── PATH 0: INSTANT — canned response, ZERO LLM calls ──
    canned = _get_canned_response(prompt)
    if canned:
        print(f"[Instant-path] Canned response, no LLM needed.")
        return _fast_respond(prompt, canned, t0, save_memory=False, tts_callback=tts_callback)

    # ── PATH 0.8: CALENDAR & DATES FIRST (Always inspect Google/Samsung Calendar on dates) ──
    # 1. Fast Scheduling: "schedule a meeting with Rahul tomorrow at 4:00 p.m."
    if any(lower_prompt.startswith(p) for p in ['schedule ', 'set up ', 'create meeting', 'create event', 'add meeting', 'add calendar event', 'add event', 'book a meeting', 'book meeting']):
        time_markers = [
            r'\btomorrow\b', r'\btoday\b', r'\byesterday\b',
            r'\b(?:on |next |this )?(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b',
            r'\b(?:on )?(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2}\b',
            r'\b(?:on )?\d{1,2}(?:st|nd|rd|th)?\s+(?:of\s+)?(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b',
            r'\bin\s+\d+\s*(?:mins?|minutes?|hours?|hrs?|days?)\b',
            r'\bat\s+\d{1,2}(?::\d{2})?\s*(?:am|pm|a\.m|p\.m)?\b',
        ]
        split_idx = -1
        for marker in time_markers:
            m_mark = re.search(marker, lower_prompt, re.IGNORECASE)
            if m_mark and (split_idx == -1 or m_mark.start() < split_idx):
                split_idx = m_mark.start()

        if split_idx != -1:
            raw_title = lower_prompt[:split_idx].strip()
            time_part = lower_prompt[split_idx:].strip()

            clean_title = re.sub(
                r'^(?:please\s+)?(?:schedule|set up|create|add|book)\s+(?:a |an )?(?:calendar )?(?:event|meeting|call|session|appointment)?\s*',
                '',
                raw_title,
                flags=re.IGNORECASE
            ).strip()

            if clean_title.lower().startswith("with "):
                clean_title = clean_title[5:].strip()

            if not clean_title or clean_title in ['a', 'an', 'the', 'my']:
                event_title = "Meeting"
            elif any(clean_title.lower().startswith(w) for w in ['meeting', 'event', 'call', 'appointment']):
                event_title = clean_title.capitalize()
            else:
                event_title = f"Meeting with {clean_title.title()}"

            print(f"[Fast-path] Scheduling calendar event: '{event_title}' at '{time_part}'")
            tool_result = core_tools.execute_tool("create_calendar_event", {
                "title": event_title,
                "start_time": time_part
            })
            return _fast_respond(prompt, tool_result, t0, tts_callback=tts_callback)

    # 2. Date Inquiries: Check calendar FIRST whenever ANY date is mentioned
    _date_regex = re.compile(
        r'\b(tomorrow|today|yesterday|monday|tuesday|wednesday|thursday|friday|saturday|sunday|'
        r'(?:next|this)\s+(?:week|weekend|monday|tuesday|wednesday|thursday|friday|saturday|sunday)|'
        r'(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2}(?:st|nd|rd|th)?|'
        r'\d{1,2}(?:st|nd|rd|th)?\s+(?:of\s+)?(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*|'
        r'\d{4}-\d{2}-\d{2})\b',
        re.IGNORECASE
    )
    date_match = _date_regex.search(lower_prompt)

    # Check if inquiry is asking about plans / events / schedule / what's happening
    _cal_intent_signals = [
        'what', 'am i', 'do i', 'have i', 'any', 'plans', 'free', 'busy', 'check', 'show',
        'tell me', 'how does', 'look like', 'schedule', 'calendar', 'agenda', 'meeting',
        'meetings', 'event', 'events', 'appointment', 'appointments', 'happening', 'doing',
        'what about', 'how about', 'what is on', "what's on", 'whats on', 'got anything'
    ]
    has_cal_intent = any(sig in lower_prompt for sig in _cal_intent_signals) or len(lower_prompt.split()) <= 4

    if date_match and has_cal_intent:
        target_date_str = date_match.group(1).strip()
        print(f"[Fast-path] Calendar date inquiry detected for '{target_date_str}'")
        if "week" in target_date_str.lower():
            tool_result = core_tools.execute_tool("get_calendar_events", {"days": 7})
        else:
            tool_result = core_tools.execute_tool("get_calendar_events", {"query_date": target_date_str})
        return _fast_respond(prompt, tool_result, t0, tts_callback=tts_callback)

    # 3. General schedule triggers (without specific date - defaults to today)
    _general_cal_triggers = [
        "what's on my calendar", "whats on my calendar", "what is on my calendar",
        "show calendar", "show my calendar", "check calendar", "check my calendar",
        "my schedule", "what's my schedule", "whats my schedule", "what is my schedule",
        "my meetings today", "what meetings do i have", "upcoming meetings",
        "upcoming events", "what do i have today", "show my events", "calendar events",
        "what are my plans", "any meetings today", "am i free today"
    ]
    if any(st == lower_prompt.rstrip("?!., ") or lower_prompt.startswith(st) for st in _general_cal_triggers):
        print("[Fast-path] General calendar schedule requested")
        tool_result = core_tools.execute_tool("get_calendar_events", {"query_date": "today"})
        return _fast_respond(prompt, tool_result, t0, tts_callback=tts_callback)

    if any(lower_prompt.startswith(p) for p in ["my schedule this week", "calendar this week", "events this week", "meetings this week", "what's my schedule this week"]):
        print("[Fast-path] Weekly calendar schedule requested")
        tool_result = core_tools.execute_tool("get_calendar_events", {"days": 7})
        return _fast_respond(prompt, tool_result, t0, tts_callback=tts_callback)

    # ── PATH 1: FAST TOOL PATH — obvious tool keyword, NO LLM at all ──
    shortcut_tool = _detect_tool_shortcut(prompt)
    if shortcut_tool:
        print(f"[Fast-path] Detected tool shortcut: {shortcut_tool}")
        tool_result = core_tools.execute_tool(shortcut_tool, {})
        _safe_print(f"       Result: {tool_result}")
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

    # ── PATH 1.58: USER PERSONALIZED DAILY ROTATION ("what I listen to everyday / more / my favorites") ──
    _clean_music = re.sub(r'^(you know what|can you|could you|please|i want to|wanna|yo|hey)\s+', '', lower_prompt).strip()
    
    _daily_triggers = [
        'listen everyday', 'listen every day', 'listen to everyday', 'listen to every day',
        'listen more', 'listen to more', 'listen to most', 'listen most',
        'what i listen', 'songs that i listen', 'music that i listen',
        'my usual songs', 'my usual music', 'my favorites', 'my favorite songs',
        'my favorite music', 'my daily songs', 'my daily music', 'songs i listen to',
        'music i listen to', 'my rotation', 'daily rotation', 'what i like to listen',
        'my top tracks', 'my spotify playlist', 'play my music', 'play my songs',
        'what i listen to', 'songs i listen everyday',
        # Hindi & Hinglish daily rotation triggers
        'mera gaana', 'mera gana', 'mere gaane', 'mere gane',
        'jo mai sunta hu', 'jo main sunta hoon', 'jo roz sunta hu',
        'mera favorite gaana', 'mera favourite gaana', 'favourite gana', 'favorite gaana',
        'apna gaana', 'daily gaane'
    ]

    if any(trigger in _clean_music for trigger in _daily_triggers):
        persona = persona_engine.get_active_persona()
        honorific = persona.honorific
        print(f"[Fast-path] User personalized daily rotation request detected: '{_clean_music}'")
        res = core_tools.execute_tool("play_user_daily_rotation", {})
        return _fast_respond(prompt, res, t0, tts_callback=tts_callback)

    # ── PATH 1.59: HINDI / HINGLISH SONG PLAY ("savan barse chalao", "alfaaz ke gaane bajao") ──
    is_hindi_play = False
    hindi_query = ""
    for suffix in [' chalao', ' bajao', ' sunao', ' lagao']:
        if _clean_music.endswith(suffix):
            is_hindi_play = True
            hindi_query = _clean_music[:-len(suffix)].strip()
            break
    if not is_hindi_play:
        for prefix in ['gaana chalao ', 'gana chalao ', 'gaana bajao ', 'gana bajao ', 'gaane bajao ', 'gaana sunao ']:
            if _clean_music.startswith(prefix):
                is_hindi_play = True
                hindi_query = _clean_music[len(prefix):].strip()
                break

    if is_hindi_play:
        # Clean query
        clean_q = re.sub(r'\b(ke gaane|ke songs|ka gaana|ka song|song|songs|gaana|gana)\b', '', hindi_query).strip()
        persona = persona_engine.get_active_persona()
        honorific = persona.honorific
        if not clean_q or any(trigger in clean_q for trigger in _daily_triggers) or clean_q in ['mera', 'mere', 'kuch', 'koi', 'acha', 'accha']:
            print(f"[Fast-path] Hindi daily rotation request: '{_clean_music}'")
            res = core_tools.execute_tool("play_user_daily_rotation", {})
            return _fast_respond(prompt, res, t0, tts_callback=tts_callback)
        else:
            print(f"[Fast-path] Hindi music play request: '{clean_q}'")
            core_tools.execute_tool("play_music", {"song_query": clean_q})
            return _fast_respond(prompt, f"Playing {clean_q} on Spotify, {honorific}.", t0, tts_callback=tts_callback)

    # ── PATH 1.6: FAST MUSIC PLAY ──
    if _clean_music.startswith("play ") or lower_prompt.startswith("play "):
        song_query = _clean_music.split(" ", 1)[1].strip("., ") if _clean_music.startswith("play ") else lower_prompt.split(" ", 1)[1].strip("., ")
        
        # Check if the query is asking for daily/personal favorites
        if any(trigger in song_query for trigger in _daily_triggers):
            print(f"[Fast-path] Daily rotation request via play: '{song_query}'")
            res = core_tools.execute_tool("play_user_daily_rotation", {})
            return _fast_respond(prompt, res, t0, tts_callback=tts_callback)

        generic_music_terms = {
            'some song', 'some songs', 'a song', 'music', 'some music',
            'something', 'something good', 'good music', 'tunes', 'some tunes',
            'random song', 'random music', 'song', 'songs', 'anything',
            'gaana', 'gana', 'gaane', 'kuch gana'
        }
        persona = persona_engine.get_active_persona()
        honorific = persona.honorific
        
        if song_query.lower() in generic_music_terms:
            print(f"[Fast-path] Generic music request detected: '{song_query}' -> playing mood/curated music")
            core_tools.execute_tool("play_music_by_mood", {})
            return _fast_respond(prompt, f"Right away, {honorific}. Playing some music for you.", t0, tts_callback=tts_callback)
            
        print(f"[Fast-path] Detected music request: {song_query}")
        core_tools.execute_tool("play_music", {"song_query": song_query})
        return _fast_respond(prompt, f"Playing {song_query} for you, {honorific}.", t0, tts_callback=tts_callback)

    # ── PATH 1.65: SPOTIFY PLAYBACK CONTROLS ──
    _spotify_now_playing_keywords = ['what am i playing', 'what\'s playing', 'whats playing', 'what am i listening', 'currently playing', 'now playing', 'what song is this', 'which song', 'on spotify', 'kaun sa gaana hai', 'kya chal raha hai']
    _spotify_pause_keywords = ['pause music', 'pause spotify', 'pause the music', 'stop music', 'stop spotify', 'stop the music', 'pause playback', 'pause', 'gaana band karo', 'gaana pause karo', 'gana band karo', 'gaane band karo', 'band karo']
    _spotify_resume_keywords = ['resume music', 'resume spotify', 'resume the music', 'continue music', 'continue playing', 'unpause', 'resume playback', 'resume', 'gaana shuru karo', 'gaana chalu karo', 'chalu karo']
    _spotify_skip_keywords = ['skip', 'next song', 'next track', 'skip song', 'skip track', 'skip this', 'play next', 'agla gaana', 'next gaana', 'gaana badlo']
    _spotify_prev_keywords = ['previous song', 'previous track', 'go back', 'last song', 'play previous', 'previous', 'pichla gaana', 'piche karo']

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

    # ── PATH 1.75: COMPREHENSIVE STATUS REPORT ──
    _status_triggers = [
        "what's my status", "whats my status", "what is my status", "status report",
        "system status", "give me a status update", "status update", "how are things",
        "brief me on my status", "current status", "what is the status", "status please"
    ]
    if any(st == lower_prompt.rstrip("?!., ") or lower_prompt.startswith(st) for st in _status_triggers):
        print("[Fast-path] Status briefing requested")
        status_text = get_status_report()
        return _fast_respond(prompt, status_text, t0, tts_callback=tts_callback)

    # ── PATH 1.8: FAST REMINDERS & TASKS ──
    # Check listing reminders
    if any(lower_prompt.startswith(p) for p in ['list reminders', 'show reminders', 'what are my reminders', 'my reminders', 'my tasks', 'list tasks', 'show tasks', 'what are my tasks']):
        tool_result = core_tools.execute_tool("list_reminders", {})
        return _fast_respond(prompt, tool_result, t0, tts_callback=tts_callback)

    # Check timed reminders in minutes: "remind me to X in Y min", "remind me in Y min to X", "set a reminder for X in Y min"
    timed_min_match = (
        re.search(r'remind me (?:to|about)?\s+(.+?)\s+in\s+(\d+)\s*(?:mins?|minutes?|m\b)', lower_prompt, re.IGNORECASE) or
        re.search(r'remind me in\s+(\d+)\s*(?:mins?|minutes?|m\b)\s*(?:to|about)?\s+(.+)', lower_prompt, re.IGNORECASE) or
        re.search(r'set (?:a )?reminder (?:for|to|about)?\s*(.+?)\s+in\s+(\d+)\s*(?:mins?|minutes?|m\b)', lower_prompt, re.IGNORECASE) or
        re.search(r'set (?:a )?reminder in\s+(\d+)\s*(?:mins?|minutes?|m\b)\s*(?:for|to|about)?\s*(.+)', lower_prompt, re.IGNORECASE)
    )
    if timed_min_match:
        groups = timed_min_match.groups()
        if groups[0].isdigit():
            minutes = int(groups[0])
            topic = groups[1].strip("., ")
        else:
            topic = groups[0].strip("., ")
            minutes = int(groups[1])
        print(f"[Fast-path] Setting dynamic reminder: '{topic}' in {minutes} min")
        core_tools.execute_tool("set_dynamic_reminder", {"minutes": minutes, "topic": topic})
        return _fast_respond(prompt, f"Right away, sir. I will remind you to {topic} in {minutes} minutes.", t0, tts_callback=tts_callback)

    # Check hour-based reminders: "remind me to X in Y hours", "remind me in Y hours to X"
    timed_hour_match = (
        re.search(r'remind me (?:to|about)?\s+(.+?)\s+in\s+(\d+)\s*(?:hours?|hrs?|h\b)', lower_prompt, re.IGNORECASE) or
        re.search(r'remind me in\s+(\d+)\s*(?:hours?|hrs?|h\b)\s*(?:to|about)?\s+(.+)', lower_prompt, re.IGNORECASE) or
        re.search(r'set (?:a )?reminder (?:for|to|about)?\s*(.+?)\s+in\s+(\d+)\s*(?:hours?|hrs?|h\b)', lower_prompt, re.IGNORECASE) or
        re.search(r'set (?:a )?reminder in\s+(\d+)\s*(?:hours?|hrs?|h\b)\s*(?:for|to|about)?\s*(.+)', lower_prompt, re.IGNORECASE)
    )
    if timed_hour_match:
        groups = timed_hour_match.groups()
        if groups[0].isdigit():
            hours = int(groups[0])
            topic = groups[1].strip("., ")
        else:
            topic = groups[0].strip("., ")
            hours = int(groups[1])
        minutes = hours * 60
        print(f"[Fast-path] Setting dynamic reminder: '{topic}' in {hours} hour(s)")
        core_tools.execute_tool("set_dynamic_reminder", {"minutes": minutes, "topic": topic})
        return _fast_respond(prompt, f"Certainly, sir. I have scheduled a reminder for {hours} hour{'s' if hours > 1 else ''} from now to {topic}.", t0, tts_callback=tts_callback)

    # General reminder without time: "remind me to buy groceries", "add task finish homework"
    if any(lower_prompt.startswith(p) for p in ["remind me to ", "remind me about ", "add task ", "add reminder "]):
        for prefix in ["remind me to ", "remind me about ", "add task ", "add reminder "]:
            if lower_prompt.startswith(prefix):
                topic = lower_prompt[len(prefix):].strip("., ")
                if topic:
                    print(f"[Fast-path] Adding general task: '{topic}'")
                    core_tools.execute_tool("add_reminder", {"task": topic})
                    return _fast_respond(prompt, f"Understood, sir. I have added '{topic}' to your task list.", t0, tts_callback=tts_callback)

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

    # ── PATH 1.865: FAST DEVELOPER COMMANDS ──
    if any(w in lower_prompt for w in commands.GIT_STATUS_TRIGGERS) or 'git status' in lower_prompt or 'project status' in lower_prompt:
        print("[Fast-path] Git Status Diff")
        target_project = ""
        if any(w in lower_prompt for w in ['all projects', 'every project', 'all repos', 'all repo']):
            target_project = "all"
        elif any(w in lower_prompt for w in ['list projects', 'which projects', 'what projects', 'show projects']):
            target_project = "list"
        else:
            try:
                from tools import developer_tools
                repos = developer_tools.discover_git_repositories()
                for rname in repos:
                    if rname in lower_prompt and rname != "jarvis":
                        target_project = rname
                        break
            except Exception:
                pass
        tool_result = core_tools.execute_tool("git_status_diff", {"repo_path": target_project} if target_project else {})
        return _fast_respond(prompt, f"{tool_result}", t0, tts_callback=tts_callback)

    if any(w in lower_prompt for w in commands.SECRET_SCAN_TRIGGERS):
        print("[Fast-path] Secret Scanner")
        target_proj = ""
        try:
            from tools import developer_tools
            repos = developer_tools.discover_git_repositories()
            for rname in repos:
                if rname in lower_prompt and rname != "jarvis":
                    target_proj = rname
                    break
        except Exception:
            pass
        tool_result = core_tools.execute_tool("scan_leaked_secrets", {"target_path": target_proj} if target_proj else {})
        return _fast_respond(prompt, f"{tool_result}", t0, tts_callback=tts_callback)

    if any(w in lower_prompt for w in commands.WORKSPACE_CLEAN_TRIGGERS):
        print("[Fast-path] Clean Dev Workspace")
        target_proj = ""
        try:
            from tools import developer_tools
            repos = developer_tools.discover_git_repositories()
            for rname in repos:
                if rname in lower_prompt and rname != "jarvis":
                    target_proj = rname
                    break
        except Exception:
            pass
        tool_result = core_tools.execute_tool("clean_dev_workspace", {"root_dir": target_proj} if target_proj else {})
        return _fast_respond(prompt, f"{tool_result}", t0, tts_callback=tts_callback)


    if any(w in lower_prompt for w in commands.MEETING_START_TRIGGERS):
        print("[Fast-path] Start Meeting Mode")
        tool_result = core_tools.execute_tool("meeting_notetaker", {"action": "start"})
        return _fast_respond(prompt, f"{tool_result}", t0, tts_callback=tts_callback)

    if any(w in lower_prompt for w in commands.MEETING_STOP_TRIGGERS):
        print("[Fast-path] Stop Meeting Mode")
        tool_result = core_tools.execute_tool("meeting_notetaker", {"action": "stop"})
        return _fast_respond(prompt, f"{tool_result}", t0, tts_callback=tts_callback)

    # ── PATH 1.868: CHIEF OF STAFF, AGENDA & EMAIL ──
    if any(w in lower_prompt for w in commands.CHIEF_OF_STAFF_TRIGGERS):
        print("[Fast-path] Chief of Staff Executive Dossier")
        import chief_of_staff
        spoken = chief_of_staff.get_spoken_chief_of_staff_briefing()
        return _fast_respond(prompt, spoken, t0, tts_callback=tts_callback)

    if any(w in lower_prompt for w in commands.AGENDA_TRIGGERS):
        print("[Fast-path] Chief of Staff Agenda")
        import chief_of_staff
        agenda = chief_of_staff.get_quick_agenda("today")
        return _fast_respond(prompt, agenda, t0, tts_callback=tts_callback)

    if any(w in lower_prompt for w in commands.EMAIL_INBOX_TRIGGERS):
        print("[Fast-path] Email Inbox Triage")
        from tools import email_tools
        triage = email_tools.triage_inbox(max_count=5)
        return _fast_respond(prompt, triage, t0, tts_callback=tts_callback)


    brightness_match = _RE_BRIGHTNESS.search(lower_prompt)
    if brightness_match:
        level = brightness_match.group(1)
        print(f"[Fast-path] Set brightness to {level}")
        tool_result = core_tools.execute_tool("set_brightness", {"level": level})
        return _fast_respond(prompt, f"Right away, sir. {tool_result}", t0, tts_callback=tts_callback)

    # ── PATH 1.88: FAST WIFI/BLUETOOTH TOGGLE ──
    if 'wifi' in lower_prompt or 'wi-fi' in lower_prompt:
        action = 'disable' if any(w in lower_prompt for w in ['off', 'disable', 'turn off', 'disconnect']) else 'enable'
        print(f"[Fast-path] WiFi: {action}")
        tool_result = core_tools.execute_tool("toggle_wifi", {"action": action})
        return _fast_respond(prompt, f"Done, sir. {tool_result}", t0, tts_callback=tts_callback)

    if 'bluetooth' in lower_prompt:
        action = 'disable' if any(w in lower_prompt for w in ['off', 'disable', 'turn off', 'disconnect']) else 'enable'
        print(f"[Fast-path] Bluetooth: {action}")
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


    # ── PATH 1.89: FAST INSTAGRAM ──
    insta_match = _RE_INSTAGRAM.search(lower_prompt)
    if insta_match:
        username = insta_match.group(1).strip()
        print(f"[Fast-path] Instagram check for: '@{username}'")
        tool_result = core_tools.execute_tool("fetch_instagram_posts", {"username": username})
        return _fast_respond(prompt, f"Here is the latest from Instagram, sir.\n{tool_result}", t0, tts_callback=tts_callback)

    # ── PATH 1.895: FAST MARKET / STOCK FORECAST & INTELLIGENCE (Amazon Chronos) ──
    if any(trigger in lower_prompt for trigger in commands.STOCK_FORECAST_TRIGGERS) or lower_prompt.startswith(('predict stock ', 'forecast stock ', 'forecast ', 'predict share ')):
        clean_target = lower_prompt
        for trig in commands.STOCK_FORECAST_TRIGGERS + ['predict stock', 'forecast stock', 'forecast', 'predict share', 'chronos']:
            clean_target = clean_target.replace(trig, '')
        clean_target = re.sub(r'\b(for|of|the|price|share|stock|in|days|next)\b', ' ', clean_target).strip()
        days_match = re.search(r'\b(\d+)\s*(?:days|day)\b', lower_prompt)
        days = int(days_match.group(1)) if days_match else 14
        clean_target = re.sub(r'\b\d+\b', '', clean_target).strip()
        if not clean_target:
            clean_target = "NIFTY"
        print(f"[Fast-path] Stock Forecast (Amazon Chronos) for: '{clean_target}' ({days} days)")
        if tts_callback:
            tts_callback(f"Analyzing {clean_target} using Amazon Chronos probabilistic market models, sir.")
        tool_result = core_tools.execute_tool("forecast_stock", {"symbol": clean_target, "days": days})
        return _fast_respond(prompt, tool_result, t0, tts_callback=tts_callback)

    # ── PATH 1.896: FAST STOCK QUOTE ──
    if any(trigger in lower_prompt for trigger in commands.STOCK_QUOTE_TRIGGERS) or lower_prompt.startswith(('stock price of ', 'price of ', 'quote for ', 'stock quote ')):
        clean_sym = lower_prompt
        for trig in commands.STOCK_QUOTE_TRIGGERS + ['stock price of', 'price of', 'quote for', 'stock quote', 'price', 'share', 'stock']:
            clean_sym = clean_sym.replace(trig, '')
        clean_sym = re.sub(r'\b(for|of|the|what is|how is|check|batao|kya hai)\b', ' ', clean_sym).strip()
        if not clean_sym:
            clean_sym = "NIFTY"
        print(f"[Fast-path] Stock Quote for: '{clean_sym}'")
        tool_result = core_tools.execute_tool("get_stock_quote", {"symbol": clean_sym})
        return _fast_respond(prompt, tool_result, t0, tts_callback=tts_callback)

    # ── PATH 1.897: FAST REVERSE FACE SEARCH (FaceOnLive / FaceSeek OSINT) ──
    if any(trigger in lower_prompt for trigger in commands.REVERSE_FACE_SEARCH_TRIGGERS) or lower_prompt.startswith(('face search', 'reverse face search')):
        print(f"[Fast-path] Reverse Face Search requested")
        path_match = re.search(r'(?:path|file|image|photo)?\s*[:=]?\s*([a-zA-Z]:[\\/][^\s"]+\.(?:jpg|jpeg|png|webp))', prompt)
        img_target = path_match.group(1) if path_match else "camera"
        if tts_callback:
            tts_callback("Executing facial recognition and reverse OSINT search, sir.")
        tool_result = core_tools.execute_tool("reverse_face_search", {"image_path": img_target})
        return _fast_respond(prompt, tool_result, t0, tts_callback=tts_callback)


    # ── PATH 1.9: FAST WEB SEARCH ──
    if lower_prompt.startswith("search ") or lower_prompt.startswith("google ") or lower_prompt.startswith("look up "):
        query = lower_prompt.split(" ", 1)[1].strip("., ")
        # Remove filler like "for" at the start
        if query.startswith("for "):
            query = query[4:].strip()
        
        print(f"[Fast-path] Web search: '{query}'")
        tool_result = core_tools.execute_tool("search_web", {"query": query})
        return _fast_respond(prompt, f"Here's what I found on the web, sir. {tool_result}", t0, tts_callback=tts_callback)

    # ── PATH 1.94: SCHOLAR / LOCAL LIBRARY QUERY ──
    _scholar_markers = ["in my library", "from my library", "in my notes", "from my notes", "in my textbook", "from my textbook", "search library for ", "query library for "]
    if any(marker in lower_prompt for marker in _scholar_markers):
        clean_query = prompt
        for marker in _scholar_markers:
            if marker in lower_prompt:
                clean_query = re.sub(re.escape(marker), "", prompt, flags=re.IGNORECASE).strip("?,. ")
                break
        print(f"[Fast-path] Scholar Library query: '{clean_query}'")
        tool_result = core_tools.execute_tool("query_library", {"query": clean_query})
        return _fast_respond(prompt, tool_result, t0, tts_callback=tts_callback)

    # ── PATH 1.95: FAST DEEP RESEARCH SWARM ──
    _deep_research_prefixes = [
        "deep research on ", "deep research ", "conduct deep research on ", "conduct research on ",
        "run deep research on ", "run a deep research on ", "research deeply ", "deep dive on ",
        "deep dive into ", "investigate deeply ", "swarm research on ", "swarm research "
    ]
    for prefix in _deep_research_prefixes:
        if lower_prompt.startswith(prefix):
            topic = lower_prompt[len(prefix):].strip("., ")
            print(f"[Fast-path] Deep Research Swarm requested on: '{topic}'")
            if tts_callback:
                tts_callback(f"Deploying deep research swarm on {topic}, sir. I'll analyze multiple sources and compile a dossier for you.")
            tool_result = core_tools.execute_tool("deep_research_swarm", {"topic": topic})
            return _fast_respond(prompt, tool_result, t0, tts_callback=tts_callback)

    # ── PATH 1.10: KNOWLEDGE QUESTIONS → AUTO WEB SEARCH ──
    _self_refs = ['yourself', 'you', 'alfred', 'your name', 'your job', 'your purpose',
                  ' my ', 'my ', ' me ', 'me?', 'about me', ' i ']
    is_self_question = any(ref in f' {lower_prompt} ' for ref in _self_refs)
    
    knowledge_match = _RE_KNOWLEDGE.match(lower_prompt)
    if knowledge_match and not is_self_question:
        query = knowledge_match.group(2).strip("?!., ")
        prefix = knowledge_match.group(1).strip()
        
        print(f"[Fast-path] Knowledge question: '{prefix} {query}' -> web search")
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
        persona = persona_engine.get_active_persona()
        user_title = persona.get_title(USER_NAME)
        if facts:
            fact_lines = "\n".join(f"  - {f['fact']}" for f in facts)
            facts_section = f"\nKNOWN FACTS ABOUT {user_title.upper()}:\n{fact_lines}"

        # Inject Knowledge Graph connections
        kg_section = ""
        try:
            import knowledge_graph
            kg_info = knowledge_graph.query_knowledge_summary(prompt)
            if kg_info:
                kg_section = f"\n{kg_info}"
        except Exception:
            pass

        # Inject Mood Tone Adaptation
        mood_instruction = ""
        try:
            import mood_engine
            mood_instruction = mood_engine.get_mood_prompt_modifier()
        except Exception:
            pass

        client, model_name = shared.get_brain(smart=True)
        
        chat_system = f"""{persona.personality_prompt} You are powered by the {model_name} model via the Groq API. You cannot perform physical tasks.

{mood_instruction}

INTELLIGENCE & BEHAVIOR GUIDELINES:
1. You are exceptionally intelligent, articulate, witty, and loyal. You think deeply, reason accurately, and speak with confidence, warmth, and charm.
2. If asked about facts, technical concepts, or general knowledge, explain clearly and insightfully. If recent verification is required, provide what you know and naturally offer to search the web if desired. Never give robotic cop-out refusals.
3. {user_title} lives in {os.getenv("ALFRED_USER_LOCATION", "an undisclosed location")}.
4. If the user appears to be talking to someone else in the background, or says something completely random that isn't directed at you, reply with EXACTLY the word "[IGNORE]". Do not say anything else.
5. Answer conversationally, concisely, and punchily (typically 1 to 3 sentences for natural voice delivery), but never sacrifice substance, wit, or intelligence.
6. You must prepend your response with an emotional mood tag reflecting the context: [MOOD: happy], [MOOD: sad], [MOOD: alert], [MOOD: calm], [MOOD: angry], or [MOOD: thinking].{facts_section}{memory_section}{kg_section}"""
        messages = [{'role': 'system', 'content': chat_system}] + _conversation_history[-6:]

        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                stream=True,
                temperature=0.6,    # Intelligent, expressive, and conversational
                max_tokens=256      # Ample room for thoughtful, complete sentences
            )
            
            speech = ""
            sentence_buffer = ""
            for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    token = chunk.choices[0].delta.content
                else:
                    continue
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
        p = persona_engine.get_active_persona()
        print(f"\n[{p.display_name} says]: {speech}  ({time.time()-t0:.1f}s)")
        
        # Auto-save to semantic memory
        _auto_save_memory(prompt, speech)
        
        return speech

    # ── PATH 2.5: MULTI-TASK ORCHESTRATOR (compound requests) ──
    try:
        import task_orchestrator
        orchestrator_result = task_orchestrator.orchestrate(prompt, tts_callback=tts_callback)
        if orchestrator_result is not None:
            # Orchestrator handled the compound request
            _conversation_history.append({'role': 'user', 'content': prompt})
            _conversation_history.append({'role': 'assistant', 'content': orchestrator_result})
            memory_engine.save_conversation_turn('user', prompt)
            memory_engine.save_conversation_turn('assistant', orchestrator_result)
            print(f"\n[Alfred says]: {orchestrator_result}  ({time.time()-t0:.1f}s)")
            _auto_save_memory(prompt, orchestrator_result)
            return orchestrator_result
    except Exception as e:
        print(f"[Orchestrator] Error: {e}, falling through to standard agent path.")

    # ── PATH 3: MULTI-AGENT ORCHESTRATION PATH ──
    print("[Manager] Analyzing task to delegate...")
    
    # Cap conversation history
    if len(_conversation_history) > _MAX_HISTORY:
        _conversation_history = _conversation_history[-_MAX_HISTORY:]
    _conversation_history.append({'role': 'user', 'content': prompt})

    # Fast keyword-based routing (instant, no LLM needed)
    _ROUTE_KEYWORDS = {
        'osint': ['search', 'news', 'weather', 'earthquake', 'quake', 'briefing', 'headlines',
                  'email lookup', 'health score', 'fetch url', 'scrape', 'deep research', 'swarm',
                  'stock', 'stocks', 'share', 'shares', 'nifty', 'sensex', 'ticker', 'chronos', 'face search', 'facesearch'],
        'system': ['app', 'open', 'launch', 'file', 'create', 'delete', 'rename', 'move',
                   'volume', 'mute', 'brightness', 'wifi', 'bluetooth', 'battery', 'lock',
                   'sleep', 'shutdown', 'screenshot', 'screen', 'mouse', 'click', 'type',
                   'keyboard', 'press', 'skill', 'mirror'],
        'memory': ['remind', 'reminder', 'task', 'todo', 'journal', 'diary', 'fact',
                   'remember', 'forget', 'library', 'recall',
                   'calendar', 'meeting', 'meetings', 'schedule', 'event', 'events', 'appointment', 'appointments'],
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
            response = chat(
                messages=messages,
                format='json',
                options={'temperature': 0},
                smart=True
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
                    res = str(core_tools.execute_tool(tool_name, kwargs))
                    print(f"       Result: {res}")
                    if res.startswith("CONFIRMATION REQUIRED"):
                        # Stop here and ask the user; never let the model talk past the gate
                        final = res.replace("CONFIRMATION REQUIRED: ", "")
                        break
                    results.append(f"Result from {tool_name}: {res}")
                    if "Error" in res or "not found" in res:
                        has_error = True
                if final:
                    break

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
    p = persona_engine.get_active_persona()
    print(f"\n[{p.display_name} says]: {final}  ({time.time()-t0:.1f}s)")
    
    # Auto-save to semantic memory
    _auto_save_memory(prompt, final)
    
    return final

