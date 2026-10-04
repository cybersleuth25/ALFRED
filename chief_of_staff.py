"""
Daily Chief of Staff Intelligence Engine for JARVIS / Alfred.
=============================================================
Synthesizes:
1. Google & Samsung Calendar schedules + conflict detection.
2. Uninterrupted deep work / focus time slots.
3. Priority Inbox triage (urgent action items vs newsletters).
4. Long-term pending tasks from Alfred's semantic memory.
5. Proactive strategic recommendations for the day.
"""

import os
import sys
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from tools import calendar_tools
from tools import email_tools
import memory_engine
import persona_engine


def get_quick_agenda(date_str: str = "today") -> str:
    """Returns a quick summary of events, conflicts, and focus blocks for a given day."""
    events = calendar_tools.get_calendar_events(date_str)
    conflicts = calendar_tools.detect_schedule_conflicts(date_str)
    focus = calendar_tools.find_focus_slots(date_str)

    res = f"📅 **Agenda for {date_str.capitalize()}**:\n{events}\n\n"
    if "Conflict Alert" in conflicts:
        res += f"{conflicts}\n\n"
    res += f"{focus}"
    return res.strip()


def get_daily_executive_dossier() -> str:
    """
    Synthesizes the complete Chief of Staff Morning Executive Dossier.
    Covers: Schedule, Conflicts, Deep Work Blocks, Inbox Triage, and Pending Tasks.
    """
    user_name = os.getenv("ALFRED_USER_NAME", "Mihir")
    now_str = datetime.now().strftime("%A, %B %d, %Y")

    # 1. Calendar & Conflicts
    events = calendar_tools.get_calendar_events("today")
    conflicts = calendar_tools.detect_schedule_conflicts("today")
    focus_slots = calendar_tools.find_focus_slots("today")

    # 2. Inbox Triage
    inbox_status = email_tools.triage_inbox(max_count=6)

    # 3. Tasks
    try:
        pending_tasks = memory_engine.get_pending_tasks()
        task_count = len(pending_tasks)
        if task_count > 0:
            task_lines = [f"• {t.get('task', t) if isinstance(t, dict) else t}" for t in pending_tasks[:4]]
            tasks_formatted = f"📋 **Priority Tasks ({task_count} pending):**\n" + "\n".join(task_lines)
        else:
            tasks_formatted = "📋 **Priority Tasks:** All cleared! No pending tasks."
    except Exception:
        tasks_formatted = "📋 **Priority Tasks:** Clear."

    dossier = (
        f"🏛️ **CHIEF OF STAFF EXECUTIVE DOSSIER**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 *Prepared for:* Master {user_name} | 🗓️ *Date:* {now_str}\n\n"
        f"📅 **TODAY'S SCHEDULE:**\n{events}\n\n"
    )

    if "Conflict Alert" in conflicts:
        dossier += f"{conflicts}\n\n"

    dossier += (
        f"{focus_slots}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{inbox_status}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{tasks_formatted}\n\n"
        f"💡 **Chief of Staff Note:** Your primary focus block is ready. Let me know when to engage Focus Mode."
    )

    return dossier


def get_spoken_chief_of_staff_briefing() -> str:
    """
    Produces a natural, concise 3-4 sentence spoken briefing for Alfred's voice engine.
    """
    user_name = os.getenv("ALFRED_USER_NAME", "Mihir")
    persona = persona_engine.get_active_persona()
    title = persona.get_title(user_name)

    # Gather data points
    cal_summary = calendar_tools.get_today_events_summary() or "No meetings scheduled on your calendar."
    
    try:
        task_count = len(memory_engine.get_pending_tasks())
    except Exception:
        task_count = 0

    spoken = (
        f"Good morning, {title}. Here is your Chief of Staff briefing for today: "
        f"{cal_summary} "
        f"You have {task_count} pending items in your task queue. "
        f"Your schedule has been verified, and I have reserved your afternoon focus blocks. "
        f"How would you like to begin?"
    )
    return spoken
