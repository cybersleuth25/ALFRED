import pytest
from datetime import datetime, timedelta
import memory_engine

def test_tasks_crud():
    """Tests CRUD operations for tasks and reminders."""
    # Initially there should be no tasks
    assert len(memory_engine.get_pending_tasks()) == 0
    assert len(memory_engine.get_due_tasks()) == 0

    # Add tasks
    now_str = datetime.now().isoformat()
    past_str = (datetime.now() - timedelta(hours=1)).isoformat()
    future_str = (datetime.now() + timedelta(hours=1)).isoformat()

    memory_engine.add_task("Clean the room", deadline=future_str)
    memory_engine.add_task("Submit report", deadline=past_str)
    memory_engine.add_task("Buy groceries") # No deadline

    pending = memory_engine.get_pending_tasks()
    assert len(pending) == 3
    tasks_names = [t["task"] for t in pending]
    assert "Clean the room" in tasks_names
    assert "Submit report" in tasks_names
    assert "Buy groceries" in tasks_names

    # Check due tasks (should only include "Submit report" because its deadline has passed)
    due = memory_engine.get_due_tasks()
    assert len(due) == 1
    assert due[0]["task"] == "Submit report"

    # Complete a task
    task_to_complete = [t for t in pending if t["task"] == "Submit report"][0]
    memory_engine.complete_task(task_to_complete["id"])

    pending_after_complete = memory_engine.get_pending_tasks()
    assert len(pending_after_complete) == 2
    assert "Submit report" not in [t["task"] for t in pending_after_complete]

    # Delete a task
    task_to_delete = [t for t in pending_after_complete if t["task"] == "Clean the room"][0]
    memory_engine.delete_task(task_to_delete["id"])

    pending_after_delete = memory_engine.get_pending_tasks()
    assert len(pending_after_delete) == 1
    assert pending_after_delete[0]["task"] == "Buy groceries"

    # Clear all tasks
    memory_engine.clear_all_tasks()
    assert len(memory_engine.get_pending_tasks()) == 0


def test_user_facts_crud():
    """Tests CRUD operations for user facts."""
    # Initially no facts
    assert len(memory_engine.get_user_facts()) == 0

    # Add facts
    memory_engine.add_user_fact("User prefers coffee over tea.")
    memory_engine.add_user_fact("User is a software engineer.")

    facts = memory_engine.get_user_facts()
    assert len(facts) == 2
    facts_texts = [f["fact"] for f in facts]
    assert "User prefers coffee over tea." in facts_texts
    assert "User is a software engineer." in facts_texts

    # Delete fact
    fact_to_delete = facts[0]
    memory_engine.delete_user_fact(fact_to_delete["id"])

    facts_remaining = memory_engine.get_user_facts()
    assert len(facts_remaining) == 1
    assert facts_remaining[0]["fact"] == "User is a software engineer."


def test_semantic_memories_and_similarity():
    """Tests storing, searching, counting, and deduplicating semantic memories."""
    # Empty count
    assert memory_engine.get_memory_count() == 0

    # Store memory
    res = memory_engine.store_memory("Alfred is a helpful butler robot developed by the Jarvis project.", category="general")
    assert res is True
    assert memory_engine.get_memory_count() == 1

    # Search memory (exact match)
    matches = memory_engine.search_memories("Alfred is a helpful butler robot developed by the Jarvis project.", top_k=1)
    assert len(matches) == 1
    assert "Alfred is a helpful butler robot" in matches[0]["content"]
    assert matches[0]["similarity"] > 0.5

    # Check near-duplicate memory prevention
    # "Alfred is a helpful butler robot developed by the Jarvis project." is already stored.
    # Storing it or a very close variant again should be rejected.
    res_dup = memory_engine.store_memory("Alfred is a helpful butler robot developed by the Jarvis project.", category="general")
    assert res_dup is False
    assert memory_engine.get_memory_count() == 1

    # Store another distinct memory
    res_new = memory_engine.store_memory("The user works as a data scientist in Paris.", category="preference")
    assert res_new is True
    assert memory_engine.get_memory_count() == 2

    # Verify recent memories
    recent = memory_engine.get_recent_memories(n=5)
    assert len(recent) == 2
    assert recent[0]["category"] == "preference"  # Last added is first (ordered by id DESC)


def test_study_sessions():
    """Tests study sessions lifecycle, focus score, distractions, stats, and streaks."""
    # Check active session when none is created
    assert memory_engine.get_active_study_session() is None

    # 1. Create a session
    session_id = memory_engine.create_study_session()
    active = memory_engine.get_active_study_session()
    assert active is not None
    assert active["id"] == session_id
    assert active["status"] == "active"

    # 2. Log distraction
    memory_engine.log_study_distraction(session_id, "phone_check", "checked WhatsApp")
    memory_engine.log_study_distraction(session_id, "web_browse", "opened YouTube")

    active_updated = memory_engine.get_active_study_session()
    assert active_updated["distractions"] == 2

    distractions = memory_engine.get_session_distractions(session_id)
    assert len(distractions) == 2
    assert distractions[0]["distraction_type"] == "phone_check"
    assert distractions[1]["distraction_type"] == "web_browse"

    # 3. End session
    memory_engine.end_study_session(session_id, briefing="Studied pytest framework", pomodoro_cycles=2)
    assert memory_engine.get_active_study_session() is None

    history = memory_engine.get_study_history(last_n=5)
    assert len(history) == 1
    session_record = history[0]
    assert session_record["id"] == session_id
    assert session_record["status"] == "completed"
    assert session_record["pomodoro_cycles"] == 2
    assert session_record["briefing"] == "Studied pytest framework"
    # distractions = 2. Penalty = max(5, 30 - duration). If duration ~ 0 or 1, penalty is ~29. Focus score = 100 - (2 * 29) = 42.
    assert session_record["focus_score"] < 100

    # 4. Aggregate stats
    stats = memory_engine.get_study_stats()
    assert stats["total_sessions"] == 1
    assert stats["total_pomodoros"] == 2

    # 5. Distraction breakdown
    breakdown = memory_engine.get_distraction_breakdown(session_id)
    assert breakdown.get("phone_check") == 1
    assert breakdown.get("web_browse") == 1

    # 6. Hourly focus data
    hourly_data = memory_engine.get_hourly_focus_data()
    assert len(hourly_data) == 24
    # The current hour should have active=True
    current_hour = datetime.now().hour
    assert hourly_data[current_hour]["active"] is True
    assert hourly_data[current_hour]["distractions"] == 2


def test_study_streaks_and_crash_recovery():
    """Tests study streak calculations and closing orphaned sessions on startup."""
    # 1. Close orphaned sessions
    # Create an active study session simulating a running daemon that crashed
    session_id_crashed = memory_engine.create_study_session()
    
    # Run close_orphaned_sessions
    memory_engine.close_orphaned_sessions()
    
    # Assert it was marked as crashed and active is empty
    assert memory_engine.get_active_study_session() is None
    history = memory_engine.get_study_history(last_n=5)
    crashed_record = [s for s in history if s["id"] == session_id_crashed][0]
    assert crashed_record["status"] == "crashed"
    assert crashed_record["focus_score"] == 0

    # 2. Study Streak
    # Clear sessions first
    conn = memory_engine._get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM study_sessions")
    conn.commit()
    conn.close()

    # Create completed session for today
    today_str = datetime.now().strftime("%Y-%m-%d")
    conn = memory_engine._get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO study_sessions (started_at, ended_at, status) VALUES (?, ?, 'completed')",
        (f"{today_str}T10:00:00", f"{today_str}T11:00:00")
    )
    # Create completed session for yesterday
    yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    cursor.execute(
        "INSERT INTO study_sessions (started_at, ended_at, status) VALUES (?, ?, 'completed')",
        (f"{yesterday_str}T10:00:00", f"{yesterday_str}T11:00:00")
    )
    # Create completed session for day before yesterday
    two_days_ago_str = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
    cursor.execute(
        "INSERT INTO study_sessions (started_at, ended_at, status) VALUES (?, ?, 'completed')",
        (f"{two_days_ago_str}T10:00:00", f"{two_days_ago_str}T11:00:00")
    )
    conn.commit()
    conn.close()

    # Streak should be 3
    assert memory_engine.get_study_streak() == 3
