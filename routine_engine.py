"""
Routine Engine — Workflow Macros for Alfred
=============================================
Allows Alfred to execute multi-step automated workflows ("Routines") chained
together with tools, applications, TTS announcements, and system states.

Routines can be triggered by voice commands, cron schedules, or REST API calls.
Custom routines can also be compiled on-the-fly from natural language prompts.
"""

import os
import time
import json
import random
import threading
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

import shared
import memory_engine
from tools import core_tools

USER_NAME = os.getenv("ALFRED_USER_NAME", "User")

# ── Built-in Routine Templates ──

DEFAULT_ROUTINES = [
    {
        "name": "morning_protocol",
        "display_name": "Morning Protocol",
        "trigger_phrases": [
            "morning protocol", "start morning protocol", "run morning protocol",
            "good morning alfred", "start my day", "morning routine"
        ],
        "description": "Morning intelligence briefing: weather forecast, tech news, pending reminders, and morning audio.",
        "steps": [
            {
                "type": "speak",
                "text": f"Good morning, Master {USER_NAME}. Initializing morning intelligence protocol."
            },
            {
                "type": "tool",
                "tool": "check_weather",
                "kwargs": {},
                "speak_result": True
            },
            {
                "type": "tool",
                "tool": "get_news",
                "kwargs": {"topic": "technology"},
                "speak_result": True
            },
            {
                "type": "tool",
                "tool": "list_reminders",
                "kwargs": {},
                "speak_result": True
            },
            {
                "type": "tool",
                "tool": "play_music",
                "kwargs": {"song_query": "morning lofi"}
            }
        ]
    },
    {
        "name": "deploy_mode",
        "display_name": "Deploy / Work Mode",
        "trigger_phrases": [
            "deploy mode", "start deploy mode", "engage deploy mode",
            "work mode", "coding mode", "dev mode"
        ],
        "description": "Developer setup: launches code editor, plays synthwave focus tracks, and initiates focus tracking.",
        "steps": [
            {
                "type": "speak",
                "text": "Deploy mode engaged. Launching your workspace, sir."
            },
            {
                "type": "app",
                "app": "code"
            },
            {
                "type": "tool",
                "tool": "play_music",
                "kwargs": {"song_query": "synthwave cyberpunk focus"}
            },
            {
                "type": "state",
                "target": "focus",
                "action": "start"
            }
        ]
    },
    {
        "name": "focus_session",
        "display_name": "Focus Session",
        "trigger_phrases": [
            "start focus session", "study session", "focus session", "deep work mode"
        ],
        "description": "Engages Protocol Omega focus tracking, pomodoro timer, and concentration music.",
        "steps": [
            {
                "type": "speak",
                "text": f"Protocol Omega initiated, Master {USER_NAME}. Distractions will be monitored."
            },
            {
                "type": "state",
                "target": "focus",
                "action": "start"
            },
            {
                "type": "tool",
                "tool": "play_music",
                "kwargs": {"song_query": "lofi hip hop study beats"}
            }
        ]
    },
    {
        "name": "night_owl",
        "display_name": "Night Owl / Wind Down",
        "trigger_phrases": [
            "night owl", "wind down", "end of day", "good night alfred", "night routine"
        ],
        "description": "Evening wrap-up: disengages focus locks, provides bedtime reminder, and halts background alarms.",
        "steps": [
            {
                "type": "speak",
                "text": f"Good evening, Master {USER_NAME}. Disengaging all focus locks for the day."
            },
            {
                "type": "state",
                "target": "focus",
                "action": "stop"
            },
            {
                "type": "speak",
                "text": "Systems are standing by. Please get some rest, sir."
            }
        ]
    }
]


def init_default_routines():
    """Initializes the built-in routines in SQLite if they don't already exist."""
    for routine in DEFAULT_ROUTINES:
        existing = memory_engine.get_routine(routine["name"])
        if not existing:
            memory_engine.save_routine(
                name=routine["name"],
                display_name=routine["display_name"],
                trigger_phrases=routine["trigger_phrases"],
                description=routine["description"],
                steps=routine["steps"],
                is_builtin=True
            )
    print(f"[Routines] System default routines verified ({len(DEFAULT_ROUTINES)} active).")


def match_voice_trigger(transcript: str) -> dict:
    """
    Checks if the user's transcript matches any routine trigger phrase.
    Returns the matched routine dict or None.
    """
    lower = transcript.lower().strip()
    routines = memory_engine.get_all_routines()

    for r in routines:
        # Check explicit routine name (e.g. "run morning_protocol" or "morning protocol")
        if r["name"].replace("_", " ") in lower or r["display_name"].lower() in lower:
            return r
        # Check custom triggers
        for trigger in r.get("trigger_phrases", []):
            if trigger.lower() in lower:
                return r

    return None


def execute_routine(name_or_id) -> str:
    """
    Executes a routine step-by-step in a background worker thread.
    Returns an immediate confirmation message.
    """
    routine = memory_engine.get_routine(name_or_id)
    if not routine:
        return f"Routine '{name_or_id}' could not be found, sir."

    name = routine["name"]
    display = routine["display_name"]

    def _worker():
        try:
            shared.push_log(f"Starting routine: {display}", "RoutineEngine")
            memory_engine.update_routine_last_run(name)

            steps = routine.get("steps", [])
            for idx, step in enumerate(steps):
                step_type = step.get("type", "").lower()
                step_num = idx + 1

                # 1. Spoken sentence step
                if step_type == "speak":
                    raw_text = step.get("text", "")
                    text = raw_text.replace("{USER_NAME}", USER_NAME)
                    shared.push_log(f"[{display} #{step_num}] Speaking announcement...", "RoutineEngine")
                    shared.safe_speak(text)

                # 2. Tool invocation step
                elif step_type == "tool":
                    tool_name = step.get("tool", "")
                    kwargs = step.get("kwargs", {})
                    shared.push_log(f"[{display} #{step_num}] Executing tool: {tool_name}", "RoutineEngine")
                    result = core_tools.execute_tool(tool_name, kwargs)

                    if step.get("speak_result", False) and result:
                        shared.safe_speak(str(result))

                # 3. Application launch step
                elif step_type == "app":
                    app_name = step.get("app", "")
                    shared.push_log(f"[{display} #{step_num}] Launching application: {app_name}", "RoutineEngine")
                    core_tools.execute_tool("launch_application", {"app_name": app_name})

                # 4. Wait / sleep step
                elif step_type == "wait":
                    sec = step.get("seconds", 2)
                    shared.push_log(f"[{display} #{step_num}] Waiting {sec}s...", "RoutineEngine")
                    time.sleep(sec)

                # 5. System State step (focus mode, lockdown, etc.)
                elif step_type == "state":
                    target = step.get("target", "").lower()
                    action = step.get("action", "start").lower()

                    if target == "focus":
                        import study_mentor
                        if action == "start":
                            study_mentor.activate()
                        elif action == "stop":
                            study_mentor.deactivate()

                    elif target == "lockdown":
                        import study_mentor
                        if action == "start":
                            study_mentor.engage_lockdown()
                        elif action == "stop":
                            study_mentor.disengage_lockdown()

                    elif target == "globe":
                        shared.push_globe(action in ["show", "open", "start", "true"])

                    elif target == "mirror":
                        shared.push_mirror_mode(action in ["show", "open", "start", "true"])

                # Inter-step short breath
                time.sleep(0.5)

            shared.push_log(f"Routine '{display}' completed successfully.", "RoutineEngine")

        except Exception as e:
            shared.push_log(f"Routine '{display}' failed at step: {e}", "RoutineEngine")
            shared.safe_speak(f"Pardon me, sir, but routine {display} encountered an error.")

    # Run in background daemon so voice/chat is non-blocking
    threading.Thread(target=_worker, daemon=True, name=f"Routine-{name}").start()
    return f"Executing {display} for you right away, sir."


def create_routine_from_prompt(prompt: str) -> dict:
    """
    Uses LLM to parse a natural language instruction into a structured routine.
    Example: "Create a routine called Relax Mode that plays lo-fi and closes discord"
    """
    client, model = shared.get_brain()
    if not client:
        return {"error": "LLM client not configured."}

    system_prompt = f"""You are Alfred's Routine Compiler. Convert the user's routine request into a valid JSON object.
Output ONLY valid raw JSON with NO markdown codeblocks.

Schema:
{{
  "name": "snake_case_name",
  "display_name": "Title Case Display Name",
  "trigger_phrases": ["phrase 1", "phrase 2"],
  "description": "Brief summary of what the routine does",
  "steps": [
    {{ "type": "speak", "text": "words to speak (use {{USER_NAME}} for user's name)" }},
    {{ "type": "tool", "tool": "tool_name", "kwargs": {{}}, "speak_result": false }},
    {{ "type": "app", "app": "app_name" }},
    {{ "type": "wait", "seconds": 2 }},
    {{ "type": "state", "target": "focus|lockdown|globe|mirror", "action": "start|stop|show|hide" }}
  ]
}}

Available Tools: check_weather, get_news (topic), list_reminders, play_music (song_query), get_now_playing, spotify_pause, spotify_resume, spotify_skip, send_whatsapp (contact_name, message), get_earthquakes, search_web (query), launch_application (app_name).
"""

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=600
        )
        raw = response.choices[0].message.content.strip()
        # Clean markdown formatting if model accidentally wraps in ```json
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            if raw.endswith("```"):
                raw = raw.rsplit("```", 1)[0]
        data = json.loads(raw.strip())

        # Save to database
        routine_id = memory_engine.save_routine(
            name=data["name"],
            display_name=data.get("display_name", data["name"].title()),
            trigger_phrases=data.get("trigger_phrases", [data["name"]]),
            description=data.get("description", ""),
            steps=data.get("steps", []),
            is_builtin=False
        )
        data["id"] = routine_id
        return data

    except Exception as e:
        return {"error": f"Failed to generate routine: {e}"}


# Initialize default routines on import
try:
    init_default_routines()
except Exception as e:
    print(f"[Routines] Initialization error: {e}")
