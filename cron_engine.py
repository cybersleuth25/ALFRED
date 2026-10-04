import time
import psutil
import schedule
import threading
import shared
import voice_engine
import datetime
import random
import os
from llm_engine import USER_NAME

# Import push notification module (optional — graceful if not available)
try:
    import telegram_notifier
    _telegram_available = telegram_notifier.is_available()
except ImportError:
    _telegram_available = False

import memory_engine

# ── Schedule Configuration (from .env) ──
def _load_schedule():
    """Reads daily schedule configuration from .env."""
    return {
        'focus_start': os.getenv('SCHEDULE_FOCUS_START', '').strip(),
        'focus_end': os.getenv('SCHEDULE_FOCUS_END', '').strip(),
        'bedtime_warning': os.getenv('SCHEDULE_BEDTIME_WARNING', '23:00').strip(),
        'briefing_time': os.getenv('SCHEDULE_BRIEFING_TIME', '').strip(),
        'debrief_time': os.getenv('SCHEDULE_DEBRIEF_TIME', '22:00').strip(),
        'lofi_on_focus': os.getenv('SCHEDULE_LOFI_ON_FOCUS', 'true').lower() == 'true',
        'hardcore_on_boot': os.getenv('HARDCORE_ON_BOOT', 'false').lower() == 'true',
    }


class AlfredCronEngine:
    def __init__(self):
        self.running = False
        self.last_battery_warning = 0
        self.schedule_config = _load_schedule()
        self._boot_sequence_done = False

    def _safe_speak(self, message: str, priority="System"):
        """Delegates to shared.safe_speak() — centralized TTS with state management."""
        return shared.safe_speak(message, author=priority)

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

    # ============================
    #  DAILY BOOT SEQUENCE
    # ============================

    def morning_boot_sequence(self):
        """Auto-engages Protocol Omega and delivers morning briefing.
        
        Triggered by SCHEDULE_FOCUS_START time. Guards against double-activation.
        """
        import study_mentor

        if study_mentor.is_active():
            print("[Cron] Morning boot: Focus Mode already active, skipping.")
            return

        print("[Cron] ☀️ Morning Boot Sequence initiated.")

        # 1. Announce the auto-activation
        boot_phrases = [
            f"Good morning, Master {USER_NAME}. It is time to begin. I am auto-engaging Protocol Omega as per your schedule.",
            f"Rise and conquer, Master {USER_NAME}. Your scheduled focus session begins now. Engaging Protocol Omega.",
            f"Morning, sir. As per your daily schedule, I am activating Focus Mode. Let us make today count.",
        ]
        self._safe_speak(random.choice(boot_phrases))

        # 2. Activate Protocol Omega
        try:
            study_mentor.activate()
            shared.push_log("Protocol Omega auto-engaged (daily schedule).", "System")
            print("[Cron] Protocol Omega auto-engaged successfully.")
        except Exception as e:
            print(f"[Cron] Auto-engage failed: {e}")
            self._safe_speak(f"I attempted to engage Protocol Omega automatically, but encountered an error, sir. You may need to activate it manually.")
            return

        # 3. Engage hardcore mode if configured
        if self.schedule_config.get('hardcore_on_boot', False):
            try:
                study_mentor.engage_hardcore()
                print("[Cron] Hardcore mode auto-engaged on boot.")
            except Exception as e:
                print(f"[Cron] Hardcore auto-engage failed: {e}")

        # 4. Push notification
        if _telegram_available:
            try:
                telegram_notifier.send_alert(f"☀️ MORNING BOOT: Protocol Omega auto-engaged at {datetime.datetime.now().strftime('%H:%M')}. Focus session started.")
            except Exception:
                pass

        self._boot_sequence_done = True

    def scheduled_briefing(self):
        """Delivers the daily intelligence briefing at the scheduled time."""
        try:
            import briefing_engine
            briefing = briefing_engine.generate_startup_briefing(USER_NAME)
            shared.push_log(briefing, "Alfred")
            self._safe_speak(briefing)
            print("[Cron] Scheduled briefing delivered.")
        except Exception as e:
            print(f"[Cron] Scheduled briefing failed: {e}")

    def scheduled_evening_debrief(self):
        """Delivers the Evening Executive Debrief at the scheduled time."""
        try:
            import debrief_engine
            debrief_engine.generate_executive_debrief(speak=True)
            print("[Cron] Scheduled evening debrief delivered.")
        except Exception as e:
            print(f"[Cron] Scheduled evening debrief failed: {e}")

    def scheduled_focus_end(self):
        """Auto-disengages Protocol Omega at the configured end time."""
        import study_mentor

        if not study_mentor.is_active():
            print("[Cron] Scheduled focus end: Focus Mode not active, skipping.")
            return

        print("[Cron] ⏰ Scheduled focus session end.")
        end_phrases = [
            f"Master {USER_NAME}, your scheduled focus session has ended. I am disengaging Protocol Omega. Well done, sir.",
            f"Time is up, sir. Your scheduled study block is complete. Disengaging Protocol Omega now.",
            f"The scheduled focus window has closed, Master {USER_NAME}. Shutting down Protocol Omega. Take a well-deserved break.",
        ]
        self._safe_speak(random.choice(end_phrases))

        try:
            study_mentor.deactivate()
            shared.push_log("Protocol Omega auto-disengaged (schedule end).", "System")
        except Exception as e:
            print(f"[Cron] Auto-disengage failed: {e}")

    def bedtime_wind_down(self):
        """Bedtime wind-down: reminds user to stop, deactivates focus if active."""
        import study_mentor

        bedtime_phrases = [
            f"Master {USER_NAME}, it is time to wind down. Your body and mind need rest to perform tomorrow. Please begin wrapping up.",
            f"Sir, your bedtime reminder. Shut the laptop, put the phone away, and get some sleep. That is an order.",
            f"It is late, Master {USER_NAME}. I am recommending you stop working now. Tomorrow's productivity depends on tonight's rest.",
        ]
        self._safe_speak(random.choice(bedtime_phrases))

        # If focus mode is still active at bedtime, gently deactivate
        if study_mentor.is_active():
            self._safe_speak("I am also disengaging Protocol Omega for the night. You have done enough today, sir.")
            try:
                study_mentor.deactivate()
            except Exception as e:
                print(f"[Cron] Bedtime deactivation failed: {e}")

        if _telegram_available:
            try:
                telegram_notifier.send_alert(f"🌙 BEDTIME: Alfred recommends winding down. Time to rest.")
            except Exception:
                pass

    def cleanup_context_snapshots(self):
        """Daily cleanup of old context snapshots to prevent database bloat."""
        try:
            memory_engine.cleanup_old_context(days=7)
            print("[Cron] Context snapshot cleanup complete.")
        except Exception as e:
            print(f"[Cron] Context cleanup failed: {e}")

    def start(self):
        self.running = True
        cfg = self.schedule_config

        # ── Standard schedules ──
        # Every 2 hours, remind about posture
        schedule.every(2).hours.do(self.posture_check)
        
        # Evening warning at 11:30 PM
        schedule.every().day.at("23:30").do(self.evening_signoff)

        # Daily context snapshot cleanup at 3 AM
        schedule.every().day.at("03:00").do(self.cleanup_context_snapshots)

        # ── Daily Boot Sequence schedules (from .env) ──
        if cfg['focus_start']:
            schedule.every().day.at(cfg['focus_start']).do(self.morning_boot_sequence)
            print(f"[Cron] Daily auto-focus scheduled at {cfg['focus_start']}")

        if cfg['focus_end']:
            schedule.every().day.at(cfg['focus_end']).do(self.scheduled_focus_end)
            print(f"[Cron] Daily auto-focus end scheduled at {cfg['focus_end']}")

        if cfg['briefing_time']:
            schedule.every().day.at(cfg['briefing_time']).do(self.scheduled_briefing)
            print(f"[Cron] Daily briefing scheduled at {cfg['briefing_time']}")

        if cfg.get('debrief_time'):
            schedule.every().day.at(cfg['debrief_time']).do(self.scheduled_evening_debrief)
            print(f"[Cron] Daily executive debrief scheduled at {cfg['debrief_time']}")

        if cfg['bedtime_warning']:
            schedule.every().day.at(cfg['bedtime_warning']).do(self.bedtime_wind_down)
            print(f"[Cron] Bedtime wind-down scheduled at {cfg['bedtime_warning']}")

        # Print active schedule summary
        active_schedules = []
        if cfg['focus_start']: active_schedules.append(f"Focus: {cfg['focus_start']}")
        if cfg['focus_end']: active_schedules.append(f"End: {cfg['focus_end']}")
        if cfg['briefing_time']: active_schedules.append(f"Briefing: {cfg['briefing_time']}")
        if cfg.get('debrief_time'): active_schedules.append(f"Debrief: {cfg['debrief_time']}")
        if cfg['bedtime_warning']: active_schedules.append(f"Bedtime: {cfg['bedtime_warning']}")
        if active_schedules:
            print(f"[Cron] Active daily schedule: {' | '.join(active_schedules)}")
        else:
            print("[Cron] No daily schedule configured (set SCHEDULE_* in .env to enable).")

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
