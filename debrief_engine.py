"""
Evening Executive Debrief Engine for JARVIS / ALFRED.
=====================================================
Synthesizes daily telemetry into a spoken executive summary and markdown dossier:
- Tasks completed vs pending from SQLite memory.
- Focus & study metrics (Protocol Omega dwell time, streak, distractions).
- Active applications and ScreenPipe window dwell intelligence.
- Security sentinel events (tripwires, acoustic alerts).
- Spoken in the voice and tone of the active persona (Alfred, Jarvis, Friday).
- Markdown debrief report written to Alfred_Workspace/debriefs/debrief_YYYY-MM-DD.md.
"""

import os
import json
import time
import datetime
import sqlite3
import psutil
from dotenv import load_dotenv

import shared
import persona_engine
import memory_engine
import voice_engine

load_dotenv()

USER_NAME = os.getenv("ALFRED_USER_NAME", "User")
DEBRIEF_DIR = os.path.join(os.path.dirname(__file__), "Alfred_Workspace", "debriefs")
os.makedirs(DEBRIEF_DIR, exist_ok=True)


def _get_todays_tasks() -> dict:
    """Retrieves tasks completed today and tasks remaining pending."""
    conn = None
    try:
        conn = memory_engine._get_connection()
        cursor = conn.cursor()
        today_str = datetime.date.today().isoformat()
        
        # Completed tasks
        cursor.execute("SELECT task, added_at FROM tasks WHERE completed = 1 AND added_at LIKE ?", (f"{today_str}%",))
        completed = [row[0] for row in cursor.fetchall()]

        # Pending tasks
        cursor.execute("SELECT task, deadline FROM tasks WHERE completed = 0")
        pending = [{"task": row[0], "deadline": row[1]} for row in cursor.fetchall()]
        
        return {"completed": completed, "pending": pending}
    except Exception as e:
        print(f"[Debrief Engine] Task retrieval error: {e}")
        return {"completed": [], "pending": []}
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def _get_todays_security_incidents() -> list:
    """Retrieves security incidents logged today."""
    conn = None
    try:
        conn = memory_engine._get_connection()
        cursor = conn.cursor()
        today_str = datetime.date.today().isoformat()
        cursor.execute("""
            SELECT incident_type, severity, details, timestamp 
            FROM security_incidents 
            WHERE timestamp LIKE ? 
            ORDER BY id DESC LIMIT 10
        """, (f"{today_str}%",))
        rows = cursor.fetchall()
        return [{"type": r[0], "severity": r[1], "details": r[2], "time": r[3]} for r in rows]
    except Exception as e:
        return []
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def _get_screenpipe_highlights() -> list:
    """Pulls recent screen memory observations logged today."""
    conn = None
    try:
        conn = memory_engine._get_connection()
        cursor = conn.cursor()
        today_str = datetime.date.today().isoformat()
        cursor.execute("""
            SELECT memory_text FROM semantic_memories 
            WHERE category = 'screen_memory' AND created_at LIKE ? 
            ORDER BY id DESC LIMIT 6
        """, (f"{today_str}%",))
        rows = cursor.fetchall()
        highlights = []
        for r in rows:
            text = r[0].replace("Screen content:", "").strip()
            if len(text) > 30:
                highlights.append(text[:120] + "...")
        return highlights
    except Exception:
        return []
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def generate_executive_debrief(speak: bool = True) -> dict:
    """
    Synthesizes and delivers the Evening Executive Debrief.
    Returns:
        {
            "success": bool,
            "spoken_text": str,
            "markdown_path": str,
            "metrics": dict
        }
    """
    today_date = datetime.date.today().strftime("%B %d, %Y")
    now_time = datetime.datetime.now().strftime("%I:%M %p")
    persona = persona_engine.get_active_persona()

    tasks_info = _get_todays_tasks()
    incidents = _get_todays_security_incidents()
    screen_notes = _get_screenpipe_highlights()

    # System metrics
    try:
        battery = psutil.sensors_battery()
        battery_pct = f"{battery.percent}% {'(Charging)' if battery.power_plugged else '(Battery)'}" if battery else "AC Powered"
    except Exception:
        battery_pct = "Nominal"

    # Focus metrics
    focus_progress = getattr(shared, "omega_daily_progress", 0)
    focus_goal = getattr(shared, "omega_daily_goal_minutes", 240)
    focus_streak = getattr(shared, "omega_streak", 0)
    distractions = getattr(shared, "omega_distractions", 0)

    telemetry = {
        "date": today_date,
        "time": now_time,
        "completed_tasks": tasks_info["completed"],
        "pending_tasks": [p["task"] for p in tasks_info["pending"]],
        "focus_minutes": focus_progress,
        "focus_goal_minutes": focus_goal,
        "study_streak_days": focus_streak,
        "distractions_blocked": distractions,
        "security_incidents_count": len(incidents),
        "battery": battery_pct,
        "recent_screen_activity": screen_notes[:3]
    }

    # Synthesize briefing using Gemini / Groq Brain
    prompt = (
        f"You are {persona.display_name}. {persona.personality_prompt}\n"
        f"Generate a spoken, podcast-style Evening Executive Debrief for {persona.honorific} {USER_NAME}.\n"
        f"Telemetry data for today ({today_date}):\n"
        f"{json.dumps(telemetry, indent=2)}\n\n"
        "Requirements:\n"
        "1. Spoken length: 3 to 5 natural paragraphs (~45-60 seconds speaking time).\n"
        "2. Congratulate them on tasks accomplished, note any pending items gently, review their focus stats, and summarize overall security status.\n"
        "3. Conclude with a warm, restorative sign-off urging rest and recharge for tomorrow.\n"
        "4. Stay in character! No markdown tags or headers in the spoken text."
    )

    spoken_script = ""
    try:
        from google import genai
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            client = genai.Client(api_key=api_key)
            resp = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )
            spoken_script = resp.text.strip()
    except Exception as e:
        print(f"[Debrief Engine] Gemini synthesis failed, falling back to Groq: {e}")

    if not spoken_script:
        # Fallback to Groq / Local Brain
        try:
            client, model_name = shared.get_brain(smart=True)
            res = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": f"You are {persona.display_name}. {persona.personality_prompt}"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7
            )
            spoken_script = res.choices[0].message.content.strip()
        except Exception as e:
            spoken_script = (
                f"Good evening, {persona.honorific}. Today is {today_date}. "
                f"You have logged {focus_progress} minutes of focus time. "
                f"All security systems remain nominal. I suggest winding down and getting some rest for tomorrow, sir."
            )

    # Save structured Markdown dossier
    filename = f"debrief_{datetime.date.today().strftime('%Y-%m-%d')}.md"
    file_path = os.path.join(DEBRIEF_DIR, filename)

    completed_md = "\n".join([f"- [x] {t}" for t in tasks_info["completed"]]) if tasks_info["completed"] else "_No tasks completed today._"
    pending_md = "\n".join([f"- [ ] {p['task']} (Due: {p.get('deadline') or 'Unspecified'})" for p in tasks_info["pending"]]) if tasks_info["pending"] else "_All tasks clear._"

    dossier = f"""# Executive Debrief — {today_date}
**Delivered by:** {persona.display_name}  
**Time of Debrief:** {now_time}  
**Status:** Nominal  

---

### Executive Spoken Brief
> {spoken_script.replace('\n', '\n> ')}

---

### Productivity & Focus Telemetry
- **Daily Focus Time:** {focus_progress} / {focus_goal} minutes ({round((focus_progress / max(1, focus_goal)) * 100)}%)
- **Study Streak:** {focus_streak} day(s)
- **Distractions Intercepted:** {distractions}

### Task Reconciliation
#### Completed Today:
{completed_md}

#### Pending Pipeline:
{pending_md}

### Sentinel & Threat Telemetry
- **Total Security Incidents Today:** {len(incidents)}
- **Power State:** {battery_pct}

---
*Generated autonomously by Alfred OS Protocol.*
"""

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(dossier)
        print(f"[Debrief Engine] Dossier written to: {file_path}")
    except Exception as e:
        print(f"[Debrief Engine] Failed to save dossier: {e}")

    # Speak and broadcast if requested
    if speak:
        shared.push_log(spoken_script, persona.display_name)
        shared.push_caption(spoken_script)
        shared.push_state("speaking")
        voice_engine.speak(spoken_script)
        shared.push_caption("")

    return {
        "success": True,
        "spoken_text": spoken_script,
        "markdown_path": file_path,
        "metrics": telemetry,
        "timestamp": now_time
    }


def get_latest_debrief() -> dict:
    """Reads the most recent debrief markdown report."""
    try:
        files = sorted([f for f in os.listdir(DEBRIEF_DIR) if f.startswith("debrief_") and f.endswith(".md")], reverse=True)
        if not files:
            return {"found": False, "content": "No debrief reports generated yet."}
        latest_file = os.path.join(DEBRIEF_DIR, files[0])
        with open(latest_file, "r", encoding="utf-8") as f:
            return {"found": True, "filename": files[0], "content": f.read()}
    except Exception as e:
        return {"found": False, "error": str(e)}


if __name__ == "__main__":
    print("Testing Evening Executive Debrief Engine (dry-run without speech)...")
    result = generate_executive_debrief(speak=False)
    print("Debrief Spoken Script Preview:\n", result["spoken_text"][:300], "...")
    print("Saved to:", result["markdown_path"])
