import time
import psutil
import schedule
import threading
import shared
import voice_engine
import datetime
import random
from llm_engine import USER_NAME

# Import push notification module (optional — graceful if not available)
try:
    import telegram_notifier
    _telegram_available = telegram_notifier.is_available()
except ImportError:
    _telegram_available = False

import memory_engine

class AlfredCronEngine:
    def __init__(self):
        self.running = False
        self.last_battery_warning = 0

    def _safe_speak(self, message: str, priority="System"):
        """
        Only speaks if Alfred is not already speaking. 
        It can safely interrupt the 'listening' state so reminders trigger immediately.
        """
        if shared.current_state != "speaking":
            old_state = shared.current_state
            # Temporarily claim the state so we don't get interrupted
            shared.push_state("speaking")
            shared.push_log(message, priority)
            shared.push_caption(message)
            voice_engine.speak(message)
            shared.push_caption("")
            shared.push_state(old_state)
            return True
        return False

    def check_battery(self):
        """Checks if battery is below 20% and not plugged in."""
        try:
            battery = psutil.sensors_battery()
            if not battery:
                return

            percent = battery.percent
            plugged = battery.power_plugged

            # If under 20% and not plugged in
            if percent <= 20 and not plugged:
                now = time.time()
                # Warn only once every 30 minutes
                if now - self.last_battery_warning > 1800:
                    success = self._safe_speak(f"Pardon the interruption sir, but your system battery is critically low at {percent}%. I strongly advise connecting to a power source.")
                    if success:
                        self.last_battery_warning = now
                    # Also push to phone
                    if _telegram_available:
                        try:
                            telegram_notifier.send_alert(f"⚠️ BATTERY LOW: {percent}% — {'Charging' if plugged else 'NOT charging'}. Plug in your charger, sir.")
                        except Exception:
                            pass
        except Exception as e:
            print(f"[Cron Error] Battery check failed: {e}")

    def posture_check(self):
        """A friendly reminder to sit up straight and drink water."""
        phrases = [
            f"Excuse me Master {USER_NAME}, you've been working for quite some time. Please remember to hydrate and adjust your posture.",
            f"A quick reminder to drink some water and stretch your legs, sir.",
            f"Pardon me sir, but it has been a few hours. I recommend a quick break to hydrate."
        ]
        self._safe_speak(random.choice(phrases))

    def evening_signoff(self):
        """Scheduled for late evening."""
        phrases = [
            f"It is getting quite late, Master {USER_NAME}. Don't forget to wrap up your tasks and get some rest.",
            f"Sir, it is half past eleven. May I suggest winding down for the night?",
            f"Pardon the interruption, but it is quite late. You should get some rest soon, sir."
        ]
        self._safe_speak(random.choice(phrases))

    def check_database_reminders(self):
        """Checks the SQLite database for tasks whose deadlines have arrived."""
        due_tasks = memory_engine.get_due_tasks()
        
        for task in due_tasks:
            phrases = [
                f"Excuse me sir, you have a scheduled task due: {task['task']}.",
                f"Master {USER_NAME}, I have a reminder for you: {task['task']}.",
                f"Pardon the interruption sir, but it is time to {task['task']}."
            ]
            success = self._safe_speak(random.choice(phrases))
            
            # If successfully spoken, mark as completed so we don't repeat
            if success:
                memory_engine.complete_task(task['id'])
                if _telegram_available:
                    try:
                        telegram_notifier.send_alert(f"⏰ REMINDER: {task['task']}")
                    except Exception:
                        pass

    def start(self):
        self.running = True
        
        # Schedule the routines
        # Every 2 hours, remind about posture
        schedule.every(2).hours.do(self.posture_check)
        
        # Evening warning at 11:30 PM
        schedule.every().day.at("23:30").do(self.evening_signoff)

        # The infinite background loop
        while self.running:
            # 1. Run time-based scheduled tasks
            schedule.run_pending()
            
            # 2. Run continuous state monitors (like battery)
            self.check_battery()
            
            # 3. Check persistent database reminders
            self.check_database_reminders()

            # Sleep so we don't fry the CPU in an infinite looping thread
            time.sleep(10)

def start_cron_daemon():
    """Spins up the Cron Engine in a detached thread."""
    engine = AlfredCronEngine()
    t = threading.Thread(target=engine.start, daemon=True, name="AlfredCronEngine")
    t.start()
    print("[System] Proactive Autonomy Engine started.")
    return engine
