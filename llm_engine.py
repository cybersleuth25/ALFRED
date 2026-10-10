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

def _agent_context_section() -> str:
    """Pending tasks, facts, memories, activity, mood and KG context for a sub-agent."""
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
    return context_section


def _build_agent_prompt(agent_name: str) -> str:
    now = datetime.now()
    time_of_day = _get_time_of_day()
    now_str = now.strftime("%A, %B %d, %Y at %I:%M %p")
    context_section = _agent_context_section()

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
    """Routes one request through the stages below; the first stage to answer wins."""
    turn = _Turn(prompt, time.time(), tts_callback)
    reply = _route_direct_address(turn)
    if reply is not None:
        return reply

    p = persona_engine.get_active_persona()
    print(f"\n[{p.display_name} is thinking...]")

    for stage in _ROUTING_STAGES:
        reply = stage(turn)
        if reply is not None:
            return reply

    if not _needs_tools(turn.prompt):
        return _chat_path(turn)
    reply = _orchestrator_path(turn)
    if reply is not None:
        return reply
    return _agent_path(turn)


class _Turn:
    """One user request as it moves through the routing stages."""

    def __init__(self, prompt: str, t0: float, tts_callback=None):
        self.t0 = t0
        self.tts_callback = tts_callback
        self.set_prompt(prompt)

    def set_prompt(self, prompt: str):
        self.prompt = prompt
        self.lower = prompt.lower().strip()

    def reply(self, speech: str, save_memory: bool = True, speak: bool = True) -> str:
        """Finish the turn through _fast_respond (history, memory, log, TTS)."""
        callback = self.tts_callback if speak else None
        return _fast_respond(self.prompt, speech, self.t0, save_memory=save_memory, tts_callback=callback)

    def say(self, text: str):
        """Speak an interim progress line before a slow tool runs."""
        if self.tts_callback:
            self.tts_callback(text)


def _run_routes(turn: _Turn, routes) -> str:
    """Try each (matcher, handler) pair in order.

    A matcher returns a falsy value to skip. A handler returns the reply, or
    None to fall through to the next route.
    """
    for matcher, handler in routes:
        match = matcher(turn)
        if match:
            reply = handler(turn, match)
            if reply is not None:
                return reply
    return None


def _contains_any(*phrases):
    return lambda turn: any(p in turn.lower for p in phrases)


def _starts_with_any(*prefixes):
    return lambda turn: turn.lower.startswith(prefixes)


def _regex_search(pattern):
    return lambda turn: pattern.search(turn.lower)


def _tool_reply(tool_name: str, kwargs: dict, template: str = "{}"):
    """Handler that runs one tool with fixed kwargs and speaks its result."""
    def handler(turn, _match):
        tool_result = core_tools.execute_tool(tool_name, kwargs)
        return turn.reply(template.format(tool_result))
    return handler


# ═══ Stage 1: direct persona addressing, intents and canned replies ═══

def _route_direct_address(turn: _Turn):
    """Handle "Friday, ..." style addressing. May rewrite the turn's prompt."""
    addressed_target, remaining_cmd = persona_engine.check_direct_address(turn.prompt)
    if not addressed_target:
        return None
    if addressed_target != persona_engine.get_active_persona().name:
        persona_engine.switch_persona(addressed_target)
    if remaining_cmd.strip():
        turn.set_prompt(remaining_cmd)
        return None
    p = persona_engine.get_active_persona()
    if addressed_target == 'friday':
        reply = f"Hey {p.honorific}, what's the plan?"
    elif addressed_target == 'jarvis':
        reply = f"At your service, {p.honorific}."
    else:
        reply = f"Alfred here, {p.get_title(USER_NAME)}."
    return turn.reply(reply)


_TIME_QUERIES = {'what time is it', 'what is the time', 'tell me the time', 'current time'}
_STUDY_CONFIRM_WORDS = ['yes', 'yeah', 'sure', 'do it', 'confirm', 'start']
_STUDY_START_PHRASES = ['i am studying', 'time to study', 'start protocol omega', 'start focus mode', 'study mode']
_STUDY_STOP_PHRASES = ['stop studying', 'stop protocol omega', 'stop focus mode', 'deactivate protocol omega']
_CREATE_ROUTINE_PREFIXES = ('create a routine', 'create routine', 'make a routine', 'new routine')
_PERSONA_MENU_PHRASES = ["switch persona", "change persona", "switch voice", "change voice", "switch personality"]


def _reply_current_time(turn, _match):
    current_time = datetime.now().strftime('%I:%M %p').lstrip('0')
    return turn.reply(f"It is currently {current_time}, sir.")


def _is_awaiting_study_confirmation(turn):
    return getattr(shared, 'awaiting_study_confirmation', False)


def _reply_study_confirmation(turn, _match):
    shared.awaiting_study_confirmation = False
    if any(w in turn.lower for w in _STUDY_CONFIRM_WORDS):
        import study_mentor
        return turn.reply(study_mentor.activate())
    return turn.reply("Very well, sir. Protocol Omega remains on standby.")


def _reply_study_start(turn, _match):
    import study_mentor
    if study_mentor.is_active():
        return turn.reply("Protocol Omega is already active, sir.")
    shared.awaiting_study_confirmation = True
    return turn.reply("Shall I initiate Protocol Omega, sir?", save_memory=False)


def _reply_study_stop(turn, _match):
    import study_mentor
    if study_mentor.is_active():
        return turn.reply(study_mentor.deactivate())
    return turn.reply("Protocol Omega is not currently active, sir.")


def _match_routine(turn):
    try:
        import routine_engine
        return routine_engine.match_voice_trigger(turn.lower)
    except Exception as e:
        print(f"[Routine Fast-Path Error] {e}")
        return None


def _reply_run_routine(turn, routine):
    try:
        import routine_engine
        print(f"[Fast-path] Matched routine: {routine['display_name']}")
        res = routine_engine.execute_routine(routine["name"])
        return turn.reply(res, speak=False)
    except Exception as e:
        print(f"[Routine Fast-Path Error] {e}")
        return None


def _reply_create_routine(turn, _match):
    try:
        import routine_engine
        res = routine_engine.create_routine_from_prompt(turn.prompt)
        if "error" in res:
            return turn.reply(f"I had difficulty compiling that routine, sir: {res['error']}")
        display = res.get("display_name", res.get("name", "Custom Routine"))
        return turn.reply(f"Routine '{display}' has been created and saved, sir. You can trigger it anytime by saying its name.")
    except Exception as e:
        return turn.reply(f"Failed to create routine, sir: {e}")


def _match_persona_switch(turn):
    return persona_engine.extract_persona_name(turn.lower)


def _reply_persona_switch(turn, target_p):
    persona_engine.switch_persona(target_p)
    p = persona_engine.get_active_persona()
    if target_p == 'friday':
        reply = f"F.R.I.D.A.Y. online and ready. What's the plan, {p.honorific}?"
    elif target_p == 'jarvis':
        reply = f"J.A.R.V.I.S. operational. At your service, {p.honorific}."
    else:
        reply = f"Alfred at your command, {p.get_title(USER_NAME)}."
    return turn.reply(reply)


def _reply_persona_menu(turn, _match):
    p = persona_engine.get_active_persona()
    available = ", ".join(persona_engine.get_persona_names())
    return turn.reply(f"Which persona would you like, {p.honorific}? Available options are: {available}.")


def _match_canned(turn):
    return _get_canned_response(turn.prompt)


def _reply_canned(turn, canned):
    print(f"[Instant-path] Canned response, no LLM needed.")
    return turn.reply(canned, save_memory=False)


_PRELUDE_ROUTES = [
    (lambda turn: turn.lower in _TIME_QUERIES, _reply_current_time),
    (_is_awaiting_study_confirmation, _reply_study_confirmation),
    (_contains_any(*_STUDY_START_PHRASES), _reply_study_start),
    (_contains_any(*_STUDY_STOP_PHRASES), _reply_study_stop),
    (_match_routine, _reply_run_routine),
    (_starts_with_any(*_CREATE_ROUTINE_PREFIXES), _reply_create_routine),
    (_match_persona_switch, _reply_persona_switch),
    (_contains_any(*_PERSONA_MENU_PHRASES), _reply_persona_menu),
    (_match_canned, _reply_canned),
]


# ═══ Stage 2a: calendar fast paths (run before keyword shortcuts) ═══

_SCHEDULE_PREFIXES = ('schedule ', 'set up ', 'create meeting', 'create event', 'add meeting',
                      'add calendar event', 'add event', 'book a meeting', 'book meeting')
_RE_SCHEDULE_TIME_MARKERS = [re.compile(p, re.IGNORECASE) for p in (
    r'\btomorrow\b', r'\btoday\b', r'\byesterday\b',
    r'\b(?:on |next |this )?(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b',
    r'\b(?:on )?(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2}\b',
    r'\b(?:on )?\d{1,2}(?:st|nd|rd|th)?\s+(?:of\s+)?(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b',
    r'\bin\s+\d+\s*(?:mins?|minutes?|hours?|hrs?|days?)\b',
    r'\bat\s+\d{1,2}(?::\d{2})?\s*(?:am|pm|a\.m|p\.m)?\b',
)]
_RE_SCHEDULE_VERB = re.compile(
    r'^(?:please\s+)?(?:schedule|set up|create|add|book)\s+(?:a |an )?(?:calendar )?(?:event|meeting|call|session|appointment)?\s*',
    re.IGNORECASE)
_RE_CAL_DATE = re.compile(
    r'\b(tomorrow|today|yesterday|monday|tuesday|wednesday|thursday|friday|saturday|sunday|'
    r'(?:next|this)\s+(?:week|weekend|monday|tuesday|wednesday|thursday|friday|saturday|sunday)|'
    r'(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2}(?:st|nd|rd|th)?|'
    r'\d{1,2}(?:st|nd|rd|th)?\s+(?:of\s+)?(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*|'
    r'\d{4}-\d{2}-\d{2})\b',
    re.IGNORECASE)
# Words suggesting the user is asking about plans / events / what's happening
_CAL_INTENT_SIGNALS = [
    'what', 'am i', 'do i', 'have i', 'any', 'plans', 'free', 'busy', 'check', 'show',
    'tell me', 'how does', 'look like', 'schedule', 'calendar', 'agenda', 'meeting',
    'meetings', 'event', 'events', 'appointment', 'appointments', 'happening', 'doing',
    'what about', 'how about', 'what is on', "what's on", 'whats on', 'got anything'
]
_GENERAL_CAL_TRIGGERS = [
    "what's on my calendar", "whats on my calendar", "what is on my calendar",
    "show calendar", "show my calendar", "check calendar", "check my calendar",
    "my schedule", "what's my schedule", "whats my schedule", "what is my schedule",
    "my meetings today", "what meetings do i have", "upcoming meetings",
    "upcoming events", "what do i have today", "show my events", "calendar events",
    "what are my plans", "any meetings today", "am i free today"
]
_WEEKLY_CAL_PREFIXES = ("my schedule this week", "calendar this week", "events this week",
                        "meetings this week", "what's my schedule this week")


def _reply_schedule_event(turn, _match):
    """'schedule a meeting with Rahul tomorrow at 4 pm' -> create_calendar_event."""
    lower = turn.lower
    starts = [m.start() for m in (p.search(lower) for p in _RE_SCHEDULE_TIME_MARKERS) if m]
    if not starts:
        return None
    split_idx = min(starts)
    time_part = lower[split_idx:].strip()
    clean_title = _RE_SCHEDULE_VERB.sub('', lower[:split_idx].strip()).strip()
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
    return turn.reply(tool_result)


def _match_calendar_date(turn):
    """Check the calendar first whenever a date is mentioned with calendar-ish intent."""
    date_match = _RE_CAL_DATE.search(turn.lower)
    has_cal_intent = any(sig in turn.lower for sig in _CAL_INTENT_SIGNALS) or len(turn.lower.split()) <= 4
    return date_match if date_match and has_cal_intent else None


def _reply_calendar_date(turn, date_match):
    target_date_str = date_match.group(1).strip()
    print(f"[Fast-path] Calendar date inquiry detected for '{target_date_str}'")
    if "week" in target_date_str.lower():
        tool_result = core_tools.execute_tool("get_calendar_events", {"days": 7})
    else:
        tool_result = core_tools.execute_tool("get_calendar_events", {"query_date": target_date_str})
    return turn.reply(tool_result)


def _matches_trigger_phrase(triggers):
    """Prompt equals a trigger (ignoring end punctuation) or starts with one."""
    return lambda turn: any(st == turn.lower.rstrip("?!., ") or turn.lower.startswith(st) for st in triggers)


def _reply_calendar_today(turn, _match):
    print("[Fast-path] General calendar schedule requested")
    return turn.reply(core_tools.execute_tool("get_calendar_events", {"query_date": "today"}))


def _reply_calendar_week(turn, _match):
    print("[Fast-path] Weekly calendar schedule requested")
    return turn.reply(core_tools.execute_tool("get_calendar_events", {"days": 7}))


_CALENDAR_ROUTES = [
    (_starts_with_any(*_SCHEDULE_PREFIXES), _reply_schedule_event),
    (_match_calendar_date, _reply_calendar_date),
    (_matches_trigger_phrase(_GENERAL_CAL_TRIGGERS), _reply_calendar_today),
    (_starts_with_any(*_WEEKLY_CAL_PREFIXES), _reply_calendar_week),
]


# ═══ Stage 3: keyword tool shortcuts ═══

def _route_tool_shortcut(turn: _Turn):
    """Obvious single-tool keyword (weather, news, battery...): run it, no LLM."""
    shortcut_tool = _detect_tool_shortcut(turn.prompt)
    if not shortcut_tool:
        return None
    print(f"[Fast-path] Detected tool shortcut: {shortcut_tool}")
    tool_result = core_tools.execute_tool(shortcut_tool, {})
    _safe_print(f"       Result: {tool_result}")
    return turn.reply(f"Here's what I found, sir. {tool_result}")


# ═══ Stage 2b: regex / keyword fast paths (run after keyword shortcuts) ═══

# -- Apps and music --

_RE_MUSIC_FILLER = re.compile(r'^(you know what|can you|could you|please|i want to|wanna|yo|hey)\s+')
_DAILY_ROTATION_TRIGGERS = [
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
_HINDI_PLAY_SUFFIXES = [' chalao', ' bajao', ' sunao', ' lagao']
_HINDI_PLAY_PREFIXES = ['gaana chalao ', 'gana chalao ', 'gaana bajao ', 'gana bajao ', 'gaane bajao ', 'gaana sunao ']
_RE_HINDI_SONG_WORDS = re.compile(r'\b(ke gaane|ke songs|ka gaana|ka song|song|songs|gaana|gana)\b')
_GENERIC_MUSIC_TERMS = {
    'some song', 'some songs', 'a song', 'music', 'some music',
    'something', 'something good', 'good music', 'tunes', 'some tunes',
    'random song', 'random music', 'song', 'songs', 'anything',
    'gaana', 'gana', 'gaane', 'kuch gana'
}


def _music_text(turn) -> str:
    """The prompt with conversational filler ("can you", "please"...) stripped."""
    return _RE_MUSIC_FILLER.sub('', turn.lower).strip()


def _reply_launch_app(turn, _match):
    """'open X', including the compound 'open X and play Y'."""
    rest = turn.lower.split(" ", 1)[1].strip("., ")
    if " and play " in rest:
        app_part, song_part = rest.split(" and play ", 1)
        app_part = app_part.strip()
        song_part = song_part.strip()
        print(f"[Fast-path] Compound command: open '{app_part}' + play '{song_part}'")
        core_tools.execute_tool("launch_application", {"app_name": app_part})
        core_tools.execute_tool("play_music", {"song_query": song_part})
        return turn.reply(f"Opening {app_part} and playing {song_part} for you, sir.")
    print(f"[Fast-path] Detected app launch: {rest}")
    core_tools.execute_tool("launch_application", {"app_name": rest})
    return turn.reply(f"Right away, sir. Opening {rest}.")


def _play_daily_rotation(turn, log_line: str):
    print(log_line)
    return turn.reply(core_tools.execute_tool("play_user_daily_rotation", {}))


def _match_daily_rotation(turn):
    music_text = _music_text(turn)
    return any(trigger in music_text for trigger in _DAILY_ROTATION_TRIGGERS)


def _reply_daily_rotation(turn, _match):
    return _play_daily_rotation(turn, f"[Fast-path] User personalized daily rotation request detected: '{_music_text(turn)}'")


def _match_hindi_play(turn):
    """'savan barse chalao' / 'gaana bajao alfaaz' -> the song query, else None."""
    music_text = _music_text(turn)
    for suffix in _HINDI_PLAY_SUFFIXES:
        if music_text.endswith(suffix):
            return music_text[:-len(suffix)].strip()
    for prefix in _HINDI_PLAY_PREFIXES:
        if music_text.startswith(prefix):
            return music_text[len(prefix):].strip()
    return None


def _reply_hindi_play(turn, hindi_query):
    clean_q = _RE_HINDI_SONG_WORDS.sub('', hindi_query).strip()
    if (not clean_q or any(trigger in clean_q for trigger in _DAILY_ROTATION_TRIGGERS)
            or clean_q in ['mera', 'mere', 'kuch', 'koi', 'acha', 'accha']):
        return _play_daily_rotation(turn, f"[Fast-path] Hindi daily rotation request: '{_music_text(turn)}'")
    honorific = persona_engine.get_active_persona().honorific
    print(f"[Fast-path] Hindi music play request: '{clean_q}'")
    core_tools.execute_tool("play_music", {"song_query": clean_q})
    return turn.reply(f"Playing {clean_q} on Spotify, {honorific}.")


def _match_play(turn):
    return _music_text(turn).startswith("play ") or turn.lower.startswith("play ")


def _reply_play(turn, _match):
    music_text = _music_text(turn)
    source = music_text if music_text.startswith("play ") else turn.lower
    song_query = source.split(" ", 1)[1].strip("., ")
    if any(trigger in song_query for trigger in _DAILY_ROTATION_TRIGGERS):
        return _play_daily_rotation(turn, f"[Fast-path] Daily rotation request via play: '{song_query}'")

    honorific = persona_engine.get_active_persona().honorific
    if song_query.lower() in _GENERIC_MUSIC_TERMS:
        print(f"[Fast-path] Generic music request detected: '{song_query}' -> playing mood/curated music")
        core_tools.execute_tool("play_music_by_mood", {})
        return turn.reply(f"Right away, {honorific}. Playing some music for you.")
    print(f"[Fast-path] Detected music request: {song_query}")
    core_tools.execute_tool("play_music", {"song_query": song_query})
    return turn.reply(f"Playing {song_query} for you, {honorific}.")


_SPOTIFY_NOW_PLAYING = ['what am i playing', 'what\'s playing', 'whats playing', 'what am i listening', 'currently playing', 'now playing', 'what song is this', 'which song', 'on spotify', 'kaun sa gaana hai', 'kya chal raha hai']
_SPOTIFY_PAUSE = ['pause music', 'pause spotify', 'pause the music', 'stop music', 'stop spotify', 'stop the music', 'pause playback', 'pause', 'gaana band karo', 'gaana pause karo', 'gana band karo', 'gaane band karo', 'band karo']
_SPOTIFY_RESUME = ['resume music', 'resume spotify', 'resume the music', 'continue music', 'continue playing', 'unpause', 'resume playback', 'resume', 'gaana shuru karo', 'gaana chalu karo', 'chalu karo']
_SPOTIFY_SKIP = ['skip', 'next song', 'next track', 'skip song', 'skip track', 'skip this', 'play next', 'agla gaana', 'next gaana', 'gaana badlo']
_SPOTIFY_PREVIOUS = ['previous song', 'previous track', 'go back', 'last song', 'play previous', 'previous', 'pichla gaana', 'piche karo']


def _spotify_control(tool_name: str, log_name: str, speech: str = None):
    """Handler for a Spotify control; speaks the tool result when no speech is given."""
    def handler(turn, _match):
        print(f"[Fast-path] Spotify: {log_name}")
        tool_result = core_tools.execute_tool(tool_name, {})
        return turn.reply(speech if speech is not None else tool_result)
    return handler


# -- Messaging, status and reminders --

def _match_whatsapp(turn):
    lower = turn.lower
    return "whatsapp" in lower or ("message" in lower and ("to " in lower or "mom" in lower or "dad" in lower))


def _reply_whatsapp(turn, _match):
    match = _RE_WHATSAPP.search(turn.lower) or _RE_WHATSAPP_SIMPLE.search(turn.lower)
    if not match:
        return None
    contact = match.group(1).strip("., ")
    message = match.group(2).strip()
    print(f"[Fast-path] WhatsApp to '{contact}': '{message}'")
    return turn.reply(core_tools.execute_tool("send_whatsapp", {"contact_name": contact, "message": message}))


_STATUS_TRIGGERS = [
    "what's my status", "whats my status", "what is my status", "status report",
    "system status", "give me a status update", "status update", "how are things",
    "brief me on my status", "current status", "what is the status", "status please"
]
_LIST_REMINDER_PREFIXES = ('list reminders', 'show reminders', 'what are my reminders', 'my reminders',
                           'my tasks', 'list tasks', 'show tasks', 'what are my tasks')
_GENERAL_REMINDER_PREFIXES = ["remind me to ", "remind me about ", "add task ", "add reminder "]


def _timed_reminder_patterns(unit: str):
    """'remind me to X in N <unit>', 'remind me in N <unit> to X', and 'set a reminder' forms."""
    return [re.compile(p, re.IGNORECASE) for p in (
        rf'remind me (?:to|about)?\s+(.+?)\s+in\s+(\d+)\s*{unit}',
        rf'remind me in\s+(\d+)\s*{unit}\s*(?:to|about)?\s+(.+)',
        rf'set (?:a )?reminder (?:for|to|about)?\s*(.+?)\s+in\s+(\d+)\s*{unit}',
        rf'set (?:a )?reminder in\s+(\d+)\s*{unit}\s*(?:for|to|about)?\s*(.+)',
    )]


_RE_REMIND_MINUTES = _timed_reminder_patterns(r'(?:mins?|minutes?|m\b)')
_RE_REMIND_HOURS = _timed_reminder_patterns(r'(?:hours?|hrs?|h\b)')


def _match_first(patterns):
    def matcher(turn):
        for pattern in patterns:
            match = pattern.search(turn.lower)
            if match:
                return match
        return None
    return matcher


def _reminder_amount_and_topic(match):
    groups = match.groups()
    if groups[0].isdigit():
        return int(groups[0]), groups[1].strip("., ")
    return int(groups[1]), groups[0].strip("., ")


def _reply_status(turn, _match):
    print("[Fast-path] Status briefing requested")
    return turn.reply(get_status_report())


def _reply_remind_minutes(turn, match):
    minutes, topic = _reminder_amount_and_topic(match)
    print(f"[Fast-path] Setting dynamic reminder: '{topic}' in {minutes} min")
    core_tools.execute_tool("set_dynamic_reminder", {"minutes": minutes, "topic": topic})
    return turn.reply(f"Right away, sir. I will remind you to {topic} in {minutes} minutes.")


def _reply_remind_hours(turn, match):
    hours, topic = _reminder_amount_and_topic(match)
    print(f"[Fast-path] Setting dynamic reminder: '{topic}' in {hours} hour(s)")
    core_tools.execute_tool("set_dynamic_reminder", {"minutes": hours * 60, "topic": topic})
    return turn.reply(f"Certainly, sir. I have scheduled a reminder for {hours} hour{'s' if hours > 1 else ''} from now to {topic}.")


def _reply_add_task(turn, _match):
    """'remind me to buy groceries' / 'add task finish homework' (no time given)."""
    for prefix in _GENERAL_REMINDER_PREFIXES:
        if turn.lower.startswith(prefix):
            topic = turn.lower[len(prefix):].strip("., ")
            if topic:
                print(f"[Fast-path] Adding general task: '{topic}'")
                core_tools.execute_tool("add_reminder", {"task": topic})
                return turn.reply(f"Understood, sir. I have added '{topic}' to your task list.")
    return None


# -- HUD views (globe, smart mirror) --

_GLOBE_SHOW_TRIGGERS = ['show me the world', 'show the world', 'show globe', 'open globe',
                        'world view', 'show map', 'earthquake map', 'global view',
                        'show earth', 'open the globe', 'tell me about the world']
_GLOBE_HIDE_TRIGGERS = ['hide globe', 'close globe', 'hide map', 'close map', 'back to chat']
_MIRROR_SHOW_TRIGGERS = ['smart mirror', 'mirror mode', 'activate mirror', 'turn on mirror']
_MIRROR_HIDE_TRIGGERS = ['exit mirror', 'close mirror', 'disable mirror', 'turn off mirror', 'normal mode']


def _hud_toggle(push_name: str, visible: bool, log_name: str, speech: str):
    def handler(turn, _match):
        print(f"[Fast-path] {log_name} view → {'SHOW' if visible else 'HIDE'}")
        getattr(shared, push_name)(visible)
        return turn.reply(speech)
    return handler


# -- OS and developer controls --

_OS_FAST_PATHS = {
    'lock my pc': ('lock_pc', {}), 'lock the pc': ('lock_pc', {}), 'lock computer': ('lock_pc', {}), 'lock my computer': ('lock_pc', {}),
    'go to sleep': ('sleep_pc', {}), 'sleep mode': ('sleep_pc', {}), 'put pc to sleep': ('sleep_pc', {}),
    'take a screenshot': ('take_screenshot', {}), 'screenshot': ('take_screenshot', {}), 'take screenshot': ('take_screenshot', {}),
    'cancel shutdown': ('cancel_shutdown', {}), 'stop shutdown': ('cancel_shutdown', {}),
}
_TOGGLE_OFF_WORDS = ['off', 'disable', 'turn off', 'disconnect']


def _match_os_control(turn):
    for trigger, tool_call in _OS_FAST_PATHS.items():
        if trigger in turn.lower:
            return tool_call
    return None


def _reply_os_control(turn, tool_call):
    tool_name, kwargs = tool_call
    print(f"[Fast-path] OS Control: {tool_name}")
    return turn.reply(f"Done, sir. {core_tools.execute_tool(tool_name, kwargs)}")


def _named_repo_in(lower: str) -> str:
    """Name of a known git repository mentioned in the prompt, or ''."""
    try:
        from tools import developer_tools
        for rname in developer_tools.discover_git_repositories():
            if rname in lower and rname != "jarvis":
                return rname
    except Exception:
        pass
    return ""


def _reply_git_status(turn, _match):
    print("[Fast-path] Git Status Diff")
    lower = turn.lower
    if any(w in lower for w in ['all projects', 'every project', 'all repos', 'all repo']):
        target_project = "all"
    elif any(w in lower for w in ['list projects', 'which projects', 'what projects', 'show projects']):
        target_project = "list"
    else:
        target_project = _named_repo_in(lower)
    tool_result = core_tools.execute_tool("git_status_diff", {"repo_path": target_project} if target_project else {})
    return turn.reply(f"{tool_result}")


def _repo_tool(tool_name: str, arg_name: str, log_name: str):
    """Developer tool scoped to a repo named in the prompt (or the default)."""
    def handler(turn, _match):
        print(f"[Fast-path] {log_name}")
        target = _named_repo_in(turn.lower)
        tool_result = core_tools.execute_tool(tool_name, {arg_name: target} if target else {})
        return turn.reply(f"{tool_result}")
    return handler


def _reply_meeting(action: str):
    def handler(turn, _match):
        print(f"[Fast-path] {action.capitalize()} Meeting Mode")
        return turn.reply(f"{core_tools.execute_tool('meeting_notetaker', {'action': action})}")
    return handler


def _reply_chief_of_staff(turn, _match):
    print("[Fast-path] Chief of Staff Executive Dossier")
    import chief_of_staff
    return turn.reply(chief_of_staff.get_spoken_chief_of_staff_briefing())


def _reply_agenda(turn, _match):
    print("[Fast-path] Chief of Staff Agenda")
    import chief_of_staff
    return turn.reply(chief_of_staff.get_quick_agenda("today"))


def _reply_email_triage(turn, _match):
    print("[Fast-path] Email Inbox Triage")
    from tools import email_tools
    return turn.reply(email_tools.triage_inbox(max_count=5))


def _reply_brightness(turn, match):
    level = match.group(1)
    print(f"[Fast-path] Set brightness to {level}")
    return turn.reply(f"Right away, sir. {core_tools.execute_tool('set_brightness', {'level': level})}")


def _radio_toggle(tool_name: str, log_name: str):
    def handler(turn, _match):
        action = 'disable' if any(w in turn.lower for w in _TOGGLE_OFF_WORDS) else 'enable'
        print(f"[Fast-path] {log_name}: {action}")
        return turn.reply(f"Done, sir. {core_tools.execute_tool(tool_name, {'action': action})}")
    return handler


def _browser_tab(tool_name: str, log_name: str):
    def handler(turn, match):
        title = match.group(1).strip()
        print(f"[Fast-path] {log_name} tab: '{title}'")
        return turn.reply(f"Done, sir. {core_tools.execute_tool(tool_name, {'title': title})}")
    return handler


# -- OSINT, market and research --

_STOCK_FORECAST_PREFIXES = ('predict stock ', 'forecast stock ', 'forecast ', 'predict share ')
_STOCK_QUOTE_PREFIXES = ('stock price of ', 'price of ', 'quote for ', 'stock quote ')
_FACE_SEARCH_PREFIXES = ('face search', 'reverse face search')
_RE_FACE_IMAGE_PATH = re.compile(r'(?:path|file|image|photo)?\s*[:=]?\s*([a-zA-Z]:[\\/][^\s"]+\.(?:jpg|jpeg|png|webp))')
_WEB_SEARCH_PREFIXES = ("search ", "google ", "look up ")
_SCHOLAR_MARKERS = ["in my library", "from my library", "in my notes", "from my notes", "in my textbook",
                    "from my textbook", "search library for ", "query library for "]
_DEEP_RESEARCH_PREFIXES = [
    "deep research on ", "deep research ", "conduct deep research on ", "conduct research on ",
    "run deep research on ", "run a deep research on ", "research deeply ", "deep dive on ",
    "deep dive into ", "investigate deeply ", "swarm research on ", "swarm research "
]
_SELF_REFS = ['yourself', 'you', 'alfred', 'your name', 'your job', 'your purpose',
              ' my ', 'my ', ' me ', 'me?', 'about me', ' i ']


def _reply_instagram(turn, match):
    username = match.group(1).strip()
    print(f"[Fast-path] Instagram check for: '@{username}'")
    tool_result = core_tools.execute_tool("fetch_instagram_posts", {"username": username})
    return turn.reply(f"Here is the latest from Instagram, sir.\n{tool_result}")


def _match_stock_forecast(turn):
    return (any(t in turn.lower for t in commands.STOCK_FORECAST_TRIGGERS)
            or turn.lower.startswith(_STOCK_FORECAST_PREFIXES))


def _reply_stock_forecast(turn, _match):
    lower = turn.lower
    clean_target = lower
    for trig in commands.STOCK_FORECAST_TRIGGERS + ['predict stock', 'forecast stock', 'forecast', 'predict share', 'chronos']:
        clean_target = clean_target.replace(trig, '')
    clean_target = re.sub(r'\b(for|of|the|price|share|stock|in|days|next)\b', ' ', clean_target).strip()
    days_match = re.search(r'\b(\d+)\s*(?:days|day)\b', lower)
    days = int(days_match.group(1)) if days_match else 14
    clean_target = re.sub(r'\b\d+\b', '', clean_target).strip() or "NIFTY"
    print(f"[Fast-path] Stock Forecast (Amazon Chronos) for: '{clean_target}' ({days} days)")
    turn.say(f"Analyzing {clean_target} using Amazon Chronos probabilistic market models, sir.")
    return turn.reply(core_tools.execute_tool("forecast_stock", {"symbol": clean_target, "days": days}))


def _match_stock_quote(turn):
    return (any(t in turn.lower for t in commands.STOCK_QUOTE_TRIGGERS)
            or turn.lower.startswith(_STOCK_QUOTE_PREFIXES))


def _reply_stock_quote(turn, _match):
    clean_sym = turn.lower
    for trig in commands.STOCK_QUOTE_TRIGGERS + ['stock price of', 'price of', 'quote for', 'stock quote', 'price', 'share', 'stock']:
        clean_sym = clean_sym.replace(trig, '')
    clean_sym = re.sub(r'\b(for|of|the|what is|how is|check|batao|kya hai)\b', ' ', clean_sym).strip() or "NIFTY"
    print(f"[Fast-path] Stock Quote for: '{clean_sym}'")
    return turn.reply(core_tools.execute_tool("get_stock_quote", {"symbol": clean_sym}))


def _match_face_search(turn):
    return (any(t in turn.lower for t in commands.REVERSE_FACE_SEARCH_TRIGGERS)
            or turn.lower.startswith(_FACE_SEARCH_PREFIXES))


def _reply_face_search(turn, _match):
    print(f"[Fast-path] Reverse Face Search requested")
    path_match = _RE_FACE_IMAGE_PATH.search(turn.prompt)
    img_target = path_match.group(1) if path_match else "camera"
    turn.say("Executing facial recognition and reverse OSINT search, sir.")
    return turn.reply(core_tools.execute_tool("reverse_face_search", {"image_path": img_target}))


def _reply_web_search(turn, _match):
    query = turn.lower.split(" ", 1)[1].strip("., ")
    if query.startswith("for "):
        query = query[4:].strip()
    print(f"[Fast-path] Web search: '{query}'")
    tool_result = core_tools.execute_tool("search_web", {"query": query})
    return turn.reply(f"Here's what I found on the web, sir. {tool_result}")


def _reply_scholar(turn, _match):
    clean_query = turn.prompt
    for marker in _SCHOLAR_MARKERS:
        if marker in turn.lower:
            clean_query = re.sub(re.escape(marker), "", turn.prompt, flags=re.IGNORECASE).strip("?,. ")
            break
    print(f"[Fast-path] Scholar Library query: '{clean_query}'")
    return turn.reply(core_tools.execute_tool("query_library", {"query": clean_query}))


def _match_deep_research(turn):
    return next((p for p in _DEEP_RESEARCH_PREFIXES if turn.lower.startswith(p)), None)


def _reply_deep_research(turn, prefix):
    topic = turn.lower[len(prefix):].strip("., ")
    print(f"[Fast-path] Deep Research Swarm requested on: '{topic}'")
    turn.say(f"Deploying deep research swarm on {topic}, sir. I'll analyze multiple sources and compile a dossier for you.")
    return turn.reply(core_tools.execute_tool("deep_research_swarm", {"topic": topic}))


def _match_knowledge_question(turn):
    """Who/what/why... questions not about the user or the assistant."""
    if any(ref in f' {turn.lower} ' for ref in _SELF_REFS):
        return None
    return _RE_KNOWLEDGE.match(turn.lower)


def _reply_knowledge_question(turn, match):
    query = match.group(2).strip("?!., ")
    prefix = match.group(1).strip()
    print(f"[Fast-path] Knowledge question: '{prefix} {query}' -> web search")
    tool_result = core_tools.execute_tool("search_web", {"query": f"{prefix} {query}"})
    if "No web results" in tool_result or "failed" in tool_result.lower():
        print("[Fast-path] Web search returned nothing, falling through to chat path.")
        return None
    return turn.reply(f"Here's what I found, sir. {tool_result}")


_FAST_PATH_ROUTES = [
    # Apps and music
    (_starts_with_any("open ", "launch ", "start "), _reply_launch_app),
    (_match_daily_rotation, _reply_daily_rotation),
    (_match_hindi_play, _reply_hindi_play),
    (_match_play, _reply_play),
    (_contains_any(*_SPOTIFY_NOW_PLAYING), _spotify_control("get_now_playing", "get now playing")),
    (_contains_any(*_SPOTIFY_PAUSE), _spotify_control("spotify_pause", "pause", "Music paused, sir.")),
    (_contains_any(*_SPOTIFY_RESUME), _spotify_control("spotify_resume", "resume", "Resuming playback, sir.")),
    (_contains_any(*_SPOTIFY_SKIP), _spotify_control("spotify_skip", "skip", "Skipping to the next track, sir.")),
    (_contains_any(*_SPOTIFY_PREVIOUS), _spotify_control("spotify_previous", "previous", "Going back to the previous track, sir.")),
    # Messaging, status and reminders
    (_match_whatsapp, _reply_whatsapp),
    (_matches_trigger_phrase(_STATUS_TRIGGERS), _reply_status),
    (_starts_with_any(*_LIST_REMINDER_PREFIXES), _tool_reply("list_reminders", {})),
    (_match_first(_RE_REMIND_MINUTES), _reply_remind_minutes),
    (_match_first(_RE_REMIND_HOURS), _reply_remind_hours),
    (_starts_with_any(*_GENERAL_REMINDER_PREFIXES), _reply_add_task),
    # HUD views
    (_contains_any(*_GLOBE_SHOW_TRIGGERS), _hud_toggle("push_globe", True, "Globe",
        "Here's your global intelligence view, sir. You can see live earthquake activity and data points around the world.")),
    (_contains_any(*_GLOBE_HIDE_TRIGGERS), _hud_toggle("push_globe", False, "Globe", "Returning to standard view, sir.")),
    (_contains_any(*_MIRROR_SHOW_TRIGGERS), _hud_toggle("push_mirror_mode", True, "Mirror", "Activating Smart Mirror interface, sir.")),
    (_contains_any(*_MIRROR_HIDE_TRIGGERS), _hud_toggle("push_mirror_mode", False, "Mirror", "Deactivating Smart Mirror interface, sir.")),
    # OS and developer controls
    (_match_os_control, _reply_os_control),
    (_contains_any(*commands.GIT_STATUS_TRIGGERS, 'git status', 'project status'), _reply_git_status),
    (_contains_any(*commands.SECRET_SCAN_TRIGGERS), _repo_tool("scan_leaked_secrets", "target_path", "Secret Scanner")),
    (_contains_any(*commands.WORKSPACE_CLEAN_TRIGGERS), _repo_tool("clean_dev_workspace", "root_dir", "Clean Dev Workspace")),
    (_contains_any(*commands.MEETING_START_TRIGGERS), _reply_meeting("start")),
    (_contains_any(*commands.MEETING_STOP_TRIGGERS), _reply_meeting("stop")),
    (_contains_any(*commands.CHIEF_OF_STAFF_TRIGGERS), _reply_chief_of_staff),
    (_contains_any(*commands.AGENDA_TRIGGERS), _reply_agenda),
    (_contains_any(*commands.EMAIL_INBOX_TRIGGERS), _reply_email_triage),
    (_regex_search(_RE_BRIGHTNESS), _reply_brightness),
    (_contains_any('wifi', 'wi-fi'), _radio_toggle("toggle_wifi", "WiFi")),
    (_contains_any('bluetooth'), _radio_toggle("toggle_bluetooth", "Bluetooth")),
    (_regex_search(_RE_CLOSE_TAB), _browser_tab("close_browser_tab", "Close")),
    (_regex_search(_RE_SWITCH_TAB), _browser_tab("switch_browser_tab", "Switch")),
    # OSINT, market and research
    (_regex_search(_RE_INSTAGRAM), _reply_instagram),
    (_match_stock_forecast, _reply_stock_forecast),
    (_match_stock_quote, _reply_stock_quote),
    (_match_face_search, _reply_face_search),
    (_starts_with_any(*_WEB_SEARCH_PREFIXES), _reply_web_search),
    (_contains_any(*_SCHOLAR_MARKERS), _reply_scholar),
    (_match_deep_research, _reply_deep_research),
    (_match_knowledge_question, _reply_knowledge_question),
]


_ROUTING_STAGES = (
    lambda turn: _run_routes(turn, _PRELUDE_ROUTES),
    lambda turn: _run_routes(turn, _CALENDAR_ROUTES),
    _route_tool_shortcut,
    lambda turn: _run_routes(turn, _FAST_PATH_ROUTES),
)


# ═══ LLM paths: chat, multi-task orchestrator, JSON agent loop ═══

def _push_user_turn(prompt: str):
    """Cap the in-memory history, then record the user's message."""
    global _conversation_history
    if len(_conversation_history) > _MAX_HISTORY:
        _conversation_history = _conversation_history[-_MAX_HISTORY:]
    _conversation_history.append({'role': 'user', 'content': prompt})


def _record_reply(turn: _Turn, speech: str) -> str:
    """Store the assistant's reply (history, DB, semantic memory) and log it."""
    _conversation_history.append({'role': 'assistant', 'content': speech})
    memory_engine.save_conversation_turn('user', turn.prompt)
    memory_engine.save_conversation_turn('assistant', speech)
    p = persona_engine.get_active_persona()
    print(f"\n[{p.display_name} says]: {speech}  ({time.time()-turn.t0:.1f}s)")
    _auto_save_memory(turn.prompt, speech)
    return speech


def _chat_context_sections(prompt: str, user_title: str) -> str:
    """Facts, semantic memories and knowledge-graph links for the chat prompt."""
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
        facts_section = f"\nKNOWN FACTS ABOUT {user_title.upper()}:\n{fact_lines}"

    kg_section = ""
    try:
        import knowledge_graph
        kg_info = knowledge_graph.query_knowledge_summary(prompt)
        if kg_info:
            kg_section = f"\n{kg_info}"
    except Exception:
        pass
    return f"{facts_section}{memory_section}{kg_section}"


def _build_chat_system_prompt(prompt: str, model_name: str) -> str:
    persona = persona_engine.get_active_persona()
    user_title = persona.get_title(USER_NAME)
    context = _chat_context_sections(prompt, user_title)
    mood_instruction = ""
    try:
        import mood_engine
        mood_instruction = mood_engine.get_mood_prompt_modifier()
    except Exception:
        pass

    return f"""{persona.personality_prompt} You are powered by the {model_name} model via the Groq API. You cannot perform physical tasks.

{mood_instruction}

INTELLIGENCE & BEHAVIOR GUIDELINES:
1. You are exceptionally intelligent, articulate, witty, and loyal. You think deeply, reason accurately, and speak with confidence, warmth, and charm.
2. If asked about facts, technical concepts, or general knowledge, explain clearly and insightfully. If recent verification is required, provide what you know and naturally offer to search the web if desired. Never give robotic cop-out refusals.
3. {user_title} lives in {os.getenv("ALFRED_USER_LOCATION", "an undisclosed location")}.
4. If the user appears to be talking to someone else in the background, or says something completely random that isn't directed at you, reply with EXACTLY the word "[IGNORE]". Do not say anything else.
5. Answer conversationally, concisely, and punchily (typically 1 to 3 sentences for natural voice delivery), but never sacrifice substance, wit, or intelligence.
6. You must prepend your response with an emotional mood tag reflecting the context: [MOOD: happy], [MOOD: sad], [MOOD: alert], [MOOD: calm], [MOOD: angry], or [MOOD: thinking].{context}"""


def _stream_chat_reply(client, model_name: str, messages: list, tts_callback=None) -> str:
    """Stream the chat completion, speaking sentence by sentence and pushing the mood tag."""
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
        if not (chunk.choices and chunk.choices[0].delta.content):
            continue
        token = chunk.choices[0].delta.content
        speech += token
        sentence_buffer += token

        # Extract the mood tag as it streams in and strip it so it is never spoken or shown
        mood_match = re.search(r'\[MOOD:\s*(\w+)\]', sentence_buffer, flags=re.IGNORECASE)
        if mood_match:
            shared.push_mood(mood_match.group(1).lower())
            full_match = mood_match.group(0)
            sentence_buffer = sentence_buffer.replace(full_match, "").lstrip()
            speech = speech.replace(full_match, "").lstrip()

        # If we hit a sentence boundary, fire the callback
        if any(sentence_buffer.endswith(p) for p in ['. ', '! ', '? ', '\n']):
            if tts_callback and sentence_buffer.strip():
                tts_callback(sentence_buffer.strip())
            sentence_buffer = ""

    if sentence_buffer.strip() and tts_callback:
        tts_callback(sentence_buffer.strip())

    speech = speech.strip()
    if not speech:
        speech = "I'm ready to assist."
        if tts_callback: tts_callback(speech)
    return speech


def _chat_path(turn: _Turn) -> str:
    """No tools needed: lightweight streamed LLM conversation."""
    print("[Chat-path] Simple conversation, using lightweight LLM.")
    _push_user_turn(turn.prompt)
    client, model_name = shared.get_brain(smart=True)
    chat_system = _build_chat_system_prompt(turn.prompt, model_name)
    messages = [{'role': 'system', 'content': chat_system}] + _conversation_history[-6:]

    try:
        speech = _stream_chat_reply(client, model_name, messages, turn.tts_callback)
        if speech == "[IGNORE]":
            print(f"\n[Chat-path] Ignored background chatter. ({time.time()-turn.t0:.1f}s)")
            # Remove the user's junk prompt from history so it doesn't pollute context
            _conversation_history.pop()
            if turn.tts_callback: turn.tts_callback("[IGNORE]")
            return "[IGNORE]"
    except Exception as e:
        print(f"[System Error] Chat failed: {e}")
        speech = "I'm here to help."
        if turn.tts_callback: turn.tts_callback(speech)

    return _record_reply(turn, speech)


def _orchestrator_path(turn: _Turn):
    """Compound requests ("do X and then Y") handled by the task orchestrator, else None."""
    try:
        import task_orchestrator
        result = task_orchestrator.orchestrate(turn.prompt, tts_callback=turn.tts_callback)
        if result is not None:
            _conversation_history.append({'role': 'user', 'content': turn.prompt})
            _conversation_history.append({'role': 'assistant', 'content': result})
            memory_engine.save_conversation_turn('user', turn.prompt)
            memory_engine.save_conversation_turn('assistant', result)
            print(f"\n[Alfred says]: {result}  ({time.time()-turn.t0:.1f}s)")
            _auto_save_memory(turn.prompt, result)
            return result
    except Exception as e:
        print(f"[Orchestrator] Error: {e}, falling through to standard agent path.")
    return None


# Fast keyword-based sub-agent routing (instant, no LLM needed); first match wins
_AGENT_ROUTE_KEYWORDS = {
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
_AGENT_MAX_ITERATIONS = 3


def _select_agent(lower_prompt: str) -> str:
    for agent, keywords in _AGENT_ROUTE_KEYWORDS.items():
        if any(kw in lower_prompt for kw in keywords):
            return agent
    return 'osint'


def _strip_json_fences(content: str) -> str:
    """Drop markdown ```json fences the model sometimes wraps its output in."""
    if content.startswith("```json"): content = content[7:]
    elif content.startswith("```"): content = content[3:]
    if content.endswith("```"): content = content[:-3]
    return content


def _run_agent_tools(agent: str, tools: list):
    """Execute the requested tools in order.

    Returns (results, has_error, confirmation). A non-empty confirmation means
    a tool hit the user-confirmation gate; the remaining tools are skipped.
    """
    results = []
    has_error = False
    for t in tools:
        tool_name = t.get("tool")
        kwargs = t.get("kwargs", {})
        print(f"[{agent.upper()}] executing tool: {tool_name}({kwargs})")
        res = str(core_tools.execute_tool(tool_name, kwargs))
        print(f"       Result: {res}")
        if res.startswith("CONFIRMATION REQUIRED"):
            return results, has_error, res.replace("CONFIRMATION REQUIRED: ", "")
        results.append(f"Result from {tool_name}: {res}")
        if "Error" in res or "not found" in res:
            has_error = True
    return results, has_error, ""


def _agent_step(agent: str, messages: list):
    """One LLM round of the JSON agent loop. Returns (final_speech, done).

    Appends the model output and tool results to `messages` when another
    round is needed.
    """
    response = chat(messages=messages, format='json', options={'temperature': 0}, smart=True)
    content = _strip_json_fences(response['message']['content'].strip())
    alfred_data = json.loads(content.strip())

    thought = alfred_data.get("thought", "")
    if thought:
        print(f"[{agent.upper()} thinks]: {thought}")
    speech_text = alfred_data.get("response", "")
    tools = alfred_data.get("tools_to_call", [])
    if not tools:
        return (speech_text if speech_text else "Task completed."), True

    results, has_error, confirmation = _run_agent_tools(agent, tools)
    if confirmation:
        # Stop here and ask the user; never let the model talk past the gate
        return confirmation, True

    messages.append({'role': 'assistant', 'content': content})
    if has_error:
        messages.append({'role': 'user', 'content': "TOOL EXECUTION FAILED with the following errors:\n" + "\n".join(results) + "\nYou must analyze why this failed and try a different approach. Output JSON with a new 'thought' and 'tools_to_call'. Do not give up."})
        return "", False  # Run again so the model can self-correct
    messages.append({'role': 'user', 'content': "TOOL RESULTS:\n" + "\n".join(results) + "\nContinue your reasoning based on these results. Output JSON with 'response' if finished, or more 'tools_to_call'."})
    if speech_text and speech_text.strip():
        return speech_text, True
    return "", False


def _agent_path(turn: _Turn) -> str:
    """Delegate to a keyword-selected sub-agent running the JSON tool loop."""
    print("[Manager] Analyzing task to delegate...")
    _push_user_turn(turn.prompt)
    target_agent = _select_agent(turn.lower)
    print(f"[Manager] Delegating to -> {target_agent.upper()} AGENT")

    agent_sys_prompt = _build_agent_prompt(target_agent)
    messages = [{'role': 'system', 'content': agent_sys_prompt}] + _conversation_history[-6:]

    final = ""
    for _ in range(_AGENT_MAX_ITERATIONS):
        try:
            final, done = _agent_step(target_agent, messages)
        except json.JSONDecodeError as e:
            print(f"[System Error] Bad JSON: {e}")
            final = "I didn't quite catch that format. Let me try again."
            break
        except Exception as e:
            print(f"[System Error] LLM call failed: {e}")
            final = "I encountered an error trying to process that."
            break
        if done:
            break

    if not final:
        final = "I'm sorry sir, I seem to have gotten stuck in a loop."
    if turn.tts_callback:
        turn.tts_callback(final)
    return _record_reply(turn, final)
