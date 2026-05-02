import time
import schedule
import sqlite3
from datetime import datetime
from win10toast_persist import ToastNotifier
import os

toaster = ToastNotifier()
DB_PATH = os.path.join(os.path.dirname(__file__), "alfred_memory.db")

def _get_connection():
    return sqlite3.connect(DB_PATH)

def check_reminders():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Watcher: Checking for pending deadlines...")
    
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Grab pending tasks with deadlines
    cursor.execute("SELECT id, task, deadline FROM tasks WHERE completed = 0 AND deadline IS NOT NULL AND deadline != ''")
    rows = cursor.fetchall()
    
    current_time = datetime.now().strftime("%H:%M")
    
    for row in rows:
        task_id = row['id']
        task_text = row['task']
        deadline = row['deadline'].strip()
        
        # Compare current 24-hr time HH:MM against deadline HH:MM
        if current_time >= deadline:
            print(f"[ALERT] Triggering desktop notification for task ID {task_id}: {task_text}")
            
            try:
                # Trigger native Windows 10 Action Center notification
                toaster.show_toast(
                    "Alfred Reminder",
                    task_text,
                    icon_path=None,  # default python icon
                    duration=None,   # Persistence
                    threaded=True
                )
            except Exception as e:
                print(f"[Error] Failed to display toast: {e}")
                
            # Clear the deadline so it doesn't fire again next minute, 
            # but leave the task pending so the user still has to manually tell Alfred "I did X"
            cursor.execute("UPDATE tasks SET deadline = NULL WHERE id = ?", (task_id,))
            conn.commit()
            
    conn.close()

# Run the check immediately, then schedule it
check_reminders()
schedule.every(60).seconds.do(check_reminders)

if __name__ == "__main__":
    print("="*50)
    print(" ALFRED WATCHER DAEMON ONLINE ".center(50, "="))
    print("="*50)
    print("Running silently in background... (Press Ctrl+C to exit)\n")
    
    while True:
        try:
            schedule.run_pending()
            time.sleep(1)
        except KeyboardInterrupt:
            print("\nWatcher shutting down.")
            break
