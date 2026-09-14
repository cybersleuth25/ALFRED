"""
Task Orchestrator — Agent-to-Agent Delegation (Swarm v2)
========================================================
Decomposes complex multi-intent user prompts into a DAG of sub-tasks,
routes each to the correct agent/tool, runs independent tasks in parallel,
chains dependent tasks sequentially, and aggregates results into one response.

Usage:
    import task_orchestrator
    result = task_orchestrator.orchestrate("search AI news and save it to my journal", tts_callback)
"""

import os
import re
import json
import time
import threading
import concurrent.futures
from datetime import datetime

import shared

# ── Constants ──
MAX_SUBTASKS = 5
SUBTASK_TIMEOUT_S = 30
RESULT_PLACEHOLDER_RE = re.compile(r'\$RESULT_(\d+)')

# ── Agent → Tool mapping (mirrors AGENT_PROFILES in llm_engine.py) ──
AGENT_TOOL_MAP = {
    "osint": [
        "check_weather", "search_web", "get_news", "get_earthquakes",
        "daily_briefing", "reverse_email_lookup", "generate_district_health_score",
        "stealth_fetch_url", "deep_research_swarm", "get_geo_news", "fetch_instagram_posts",
    ],
    "system": [
        "create_file", "delete_file", "rename_file", "move_file", "organize_workspace",
        "launch_application", "toggle_system_volume", "play_music", "play_music_by_mood",
        "get_battery_status", "set_brightness", "toggle_wifi", "toggle_bluetooth",
        "lock_pc", "sleep_pc", "shutdown_pc", "set_volume", "take_screenshot",
        "analyze_screen", "get_screen_info", "mouse_move_and_click",
        "keyboard_type", "keyboard_press", "keyboard_hotkey", "learn_new_skill",
        "read_screen_text", "locate_object_in_camera", "locate_object_on_screen",
    ],
    "memory": [
        "set_dynamic_reminder", "add_reminder", "list_reminders", "complete_reminder",
        "delete_reminder", "clear_all_reminders", "remember_fact", "forget_fact",
        "journal_entry", "read_journal", "query_library", "recall_memories",
        "query_knowledge_graph", "extract_knowledge_from_text",
    ],
    "communications": [
        "send_whatsapp",
    ],
    "browser": [
        "list_browser_tabs", "close_browser_tab", "switch_browser_tab",
        "open_browser_tab", "read_browser_tab",
    ],
}

# Flat set for validation
ALL_KNOWN_TOOLS = set()
for tools in AGENT_TOOL_MAP.values():
    ALL_KNOWN_TOOLS.update(tools)

# Reverse map: tool_name → agent
TOOL_TO_AGENT = {}
for agent, tools in AGENT_TOOL_MAP.items():
    for tool in tools:
        TOOL_TO_AGENT[tool] = agent


def _build_decomposition_prompt(user_prompt: str) -> str:
    """Builds the LLM prompt that asks the model to decompose a user request."""
    tool_list_str = ", ".join(sorted(ALL_KNOWN_TOOLS))
    return f"""You are Alfred's Task Decomposition Engine. Your job is to break a complex user request into independent sub-tasks.

AVAILABLE TOOLS: {tool_list_str}

RULES:
1. Output valid JSON with a single key "tasks" containing an array.
2. Each task object has: "id" (int, starting from 0), "description" (str), "tool" (str, must be from AVAILABLE TOOLS), "kwargs" (dict), "depends_on" (array of task ids this task needs to complete first).
3. If a task needs the result of a previous task, use "$RESULT_N" as a placeholder in kwargs where N is the id of the dependency task.
4. Maximum {MAX_SUBTASKS} tasks. If the request only needs 1 tool, output just 1 task.
5. Only decompose into MULTIPLE tasks if the user clearly wants MULTIPLE distinct actions (separated by "and", "then", "also", "after that", etc.).
6. If the request is simple (single intent), output exactly 1 task.
7. Do NOT invent tasks the user did not ask for.
8. Do NOT use tools that don't exist in AVAILABLE TOOLS.

USER REQUEST: "{user_prompt}"

Respond with ONLY the JSON object, no markdown, no explanation."""


def _is_compound_request(prompt: str) -> bool:
    """
    Heuristic check: does the prompt contain multiple distinct intents?
    Returns True if the prompt likely needs decomposition.
    """
    lower = prompt.lower().strip()

    # Conjunctions that signal multiple intents
    compound_patterns = [
        r'\band\s+(?:also|then|after that)\b',   # "and also", "and then"
        r'\bthen\s+\b',                           # "then do X"
        r'\bafter that\b',                        # "after that"
        r'\balso\s+\b',                           # "also do X"
        r'\bplus\s+\b',                           # "plus do X"
    ]

    # Simple "and" between two verb phrases (most common case)
    # Match: "search X and play Y", "do X and save Y"
    verb_and_verb = re.search(
        r'\b(search|find|look up|play|open|launch|save|send|message|remind|set|create|delete|close|read|check|get|fetch|list|toggle|mute|lock|journal|remember)\b'
        r'.+?\band\b\s+'
        r'(search|find|look up|play|open|launch|save|send|message|remind|set|create|delete|close|read|check|get|fetch|list|toggle|mute|lock|journal|remember)\b',
        lower
    )

    if verb_and_verb:
        return True

    for pattern in compound_patterns:
        if re.search(pattern, lower):
            return True

    return False


def decompose_prompt(user_prompt: str) -> list:
    """
    Uses the LLM to decompose a complex prompt into sub-tasks.
    Returns a list of task dicts with keys: id, description, tool, kwargs, depends_on.
    Falls back to empty list on failure.
    """
    try:
        from llm_engine import chat
        decomp_prompt = _build_decomposition_prompt(user_prompt)

        response = chat(
            messages=[
                {"role": "system", "content": "You are a precise JSON task decomposer. Output only valid JSON."},
                {"role": "user", "content": decomp_prompt},
            ],
            format='json',
            options={'temperature': 0},
        )

        content = response['message']['content'].strip()

        # Strip markdown fences if model hallucinates them
        if content.startswith("```json"):
            content = content[7:]
        elif content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]

        data = json.loads(content.strip())
        tasks = data.get("tasks", [])

        # Validate and cap
        validated = []
        for t in tasks[:MAX_SUBTASKS]:
            task_id = t.get("id", len(validated))
            tool = t.get("tool", "")
            kwargs = t.get("kwargs", {})
            depends_on = t.get("depends_on", [])
            description = t.get("description", "")

            # Skip tasks with unknown tools
            if tool not in ALL_KNOWN_TOOLS:
                shared.push_log(f"Orchestrator: Skipping unknown tool '{tool}'", "System")
                continue

            # Ensure depends_on only references valid prior task ids
            valid_deps = [d for d in depends_on if isinstance(d, int) and d < task_id]

            validated.append({
                "id": task_id,
                "description": description,
                "tool": tool,
                "kwargs": kwargs,
                "depends_on": valid_deps,
            })

        return validated

    except json.JSONDecodeError as e:
        shared.push_log(f"Orchestrator: JSON parse error: {e}", "System")
        return []
    except Exception as e:
        shared.push_log(f"Orchestrator: Decomposition failed: {e}", "System")
        return []


def _resolve_placeholders(kwargs: dict, results: dict) -> dict:
    """
    Replaces $RESULT_N placeholders in kwargs values with actual results.
    """
    resolved = {}
    for key, value in kwargs.items():
        if isinstance(value, str):
            def _replacer(match):
                dep_id = int(match.group(1))
                return results.get(dep_id, f"[No result from task {dep_id}]")
            resolved[key] = RESULT_PLACEHOLDER_RE.sub(_replacer, value)
        else:
            resolved[key] = value
    return resolved


def execute_task_graph(tasks: list) -> dict:
    """
    Executes a DAG of sub-tasks with dependency resolution.
    Independent tasks run in parallel; dependent tasks wait for prerequisites.

    Returns: dict mapping task_id → result string
    """
    from tools.core_tools import execute_tool

    if not tasks:
        return {}

    results = {}            # task_id → result string
    results_lock = threading.Lock()
    completed = set()       # set of completed task_ids
    completed_event = {}    # task_id → threading.Event

    # Create completion events for each task
    for task in tasks:
        completed_event[task["id"]] = threading.Event()

    def _run_task(task: dict):
        """Execute a single sub-task after waiting for dependencies."""
        task_id = task["id"]
        tool_name = task["tool"]
        raw_kwargs = task["kwargs"]
        deps = task["depends_on"]

        # Wait for all dependencies to complete (with timeout)
        for dep_id in deps:
            if dep_id in completed_event:
                success = completed_event[dep_id].wait(timeout=SUBTASK_TIMEOUT_S)
                if not success:
                    with results_lock:
                        results[task_id] = f"Timeout waiting for task {dep_id}"
                        completed.add(task_id)
                        completed_event[task_id].set()
                    return

        # Resolve any $RESULT_N placeholders
        with results_lock:
            resolved_kwargs = _resolve_placeholders(raw_kwargs, results)

        agent = TOOL_TO_AGENT.get(tool_name, "unknown")
        shared.push_log(
            f"Orchestrator: [{agent.upper()}] executing {tool_name}({resolved_kwargs})",
            "System"
        )

        try:
            result = execute_tool(tool_name, resolved_kwargs)
        except Exception as e:
            result = f"Error: {e}"

        with results_lock:
            results[task_id] = result
            completed.add(task_id)
            completed_event[task_id].set()

        shared.push_log(
            f"Orchestrator: [{agent.upper()}] {tool_name} -> done",
            "System"
        )

    # Submit all tasks to thread pool — dependency waiting happens inside each task
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_SUBTASKS) as executor:
        futures = []
        for task in tasks:
            future = executor.submit(_run_task, task)
            futures.append(future)

        # Wait for all tasks to complete (with global timeout)
        concurrent.futures.wait(futures, timeout=SUBTASK_TIMEOUT_S * 2)

    return results


def _build_summary_prompt(user_prompt: str, tasks: list, results: dict) -> str:
    """Builds a prompt for the LLM to aggregate all sub-task results into one response."""
    task_results = []
    for task in tasks:
        tid = task["id"]
        result = results.get(tid, "No result")
        # Truncate long results to prevent prompt overflow
        if len(result) > 2000:
            result = result[:2000] + "... [truncated]"
        task_results.append(f"Task {tid} ({task['description']}): {result}")

    return f"""You are Alfred, the AI butler. The user asked: "{user_prompt}"

You delegated this to multiple sub-agents. Here are their results:
{chr(10).join(task_results)}

Now write a brief, elegant spoken response summarizing what was accomplished. 
Keep it to 2-3 sentences max. Be concise and butler-like. 
Do NOT repeat raw data — just confirm what was done.
Do NOT use markdown formatting — this will be spoken aloud."""


def orchestrate(prompt: str, tts_callback=None) -> str:
    """
    Main entry point for multi-task orchestration.
    1. Decomposes the prompt into sub-tasks
    2. Executes the task DAG
    3. Aggregates results into a spoken response

    Returns: final response string
    """
    t0 = time.time()

    # Check if this is actually a compound request
    if not _is_compound_request(prompt):
        return None  # Signal to caller: not a compound request, use normal flow

    shared.push_log("Orchestrator: Analyzing multi-intent request...", "System")

    # Step 1: Decompose
    tasks = decompose_prompt(prompt)
    if not tasks:
        shared.push_log("Orchestrator: Decomposition returned no tasks, falling through.", "System")
        return None  # Fall through to normal flow

    if len(tasks) <= 1:
        # Single task — no need for orchestration overhead, let normal flow handle it
        shared.push_log("Orchestrator: Single task detected, using normal flow.", "System")
        return None

    shared.push_log(
        f"Orchestrator: Decomposed into {len(tasks)} sub-tasks: "
        + ", ".join(f"[{t['tool']}]" for t in tasks),
        "System"
    )

    # Step 2: Execute task graph
    results = execute_task_graph(tasks)

    # Step 3: Aggregate results into a spoken summary
    try:
        from llm_engine import chat
        summary_prompt = _build_summary_prompt(prompt, tasks, results)

        response = chat(
            messages=[
                {"role": "system", "content": "You are Alfred, a concise AI butler. Respond in 2-3 spoken sentences."},
                {"role": "user", "content": summary_prompt},
            ],
            options={'temperature': 0.3},
        )
        final = response['message']['content'].strip()
    except Exception as e:
        # Fallback: just list what was done
        shared.push_log(f"Orchestrator: Summary generation failed: {e}", "System")
        done_items = [t['description'] for t in tasks if t['id'] in results]
        final = f"Done, sir. I completed {len(done_items)} tasks: " + ", ".join(done_items) + "."

    elapsed = time.time() - t0
    shared.push_log(f"Orchestrator: All tasks complete in {elapsed:.1f}s", "System")

    if tts_callback:
        tts_callback(final)

    return final
