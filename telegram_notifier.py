"""
Telegram Push Notification Module for Alfred.
==============================================
Any module in Alfred can import this and send proactive alerts to the user's phone:

    from telegram_notifier import send_alert, send_photo_alert
    send_alert("Battery critically low at 12%, sir!")
    send_photo_alert("C:/path/to/screenshot.png", "Your PC screen right now, sir.")

This module works independently of the Telegram bot polling loop.
"""

import os
import asyncio
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_ALLOWED_USER_ID")

_bot_instance = None


def _get_bot():
    """Lazy-initialize a telegram.Bot singleton."""
    global _bot_instance
    if _bot_instance is None:
        try:
            from telegram import Bot
            if TELEGRAM_BOT_TOKEN and not TELEGRAM_BOT_TOKEN.startswith("your_"):
                _bot_instance = Bot(token=TELEGRAM_BOT_TOKEN)
            else:
                print("[Telegram Notifier] No valid bot token found.")
                return None
        except ImportError:
            print("[Telegram Notifier] python-telegram-bot not installed.")
            return None
        except Exception as e:
            print(f"[Telegram Notifier] Init failed: {e}")
            return None
    return _bot_instance


def _run_async(coro):
    """Run an async coroutine from synchronous code safely."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    
    if loop and loop.is_running():
        # We're inside an existing event loop (e.g., the Telegram polling loop)
        # Schedule the coroutine as a task instead
        import threading
        result = [None]
        exception = [None]
        
        def _thread_runner():
            new_loop = asyncio.new_event_loop()
            try:
                result[0] = new_loop.run_until_complete(coro)
            except Exception as e:
                exception[0] = e
            finally:
                new_loop.close()
        
        t = threading.Thread(target=_thread_runner, daemon=True)
        t.start()
        t.join(timeout=15)
        if exception[0]:
            raise exception[0]
        return result[0]
    else:
        return asyncio.run(coro)


async def _send_message_async(text: str):
    """Send a text message to the user's Telegram chat."""
    bot = _get_bot()
    if not bot or not TELEGRAM_CHAT_ID:
        return False
    try:
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text)
        return True
    except Exception as e:
        print(f"[Telegram Notifier] Send failed: {e}")
        return False


async def _send_photo_async(filepath: str, caption: str = ""):
    """Send a photo to the user's Telegram chat."""
    bot = _get_bot()
    if not bot or not TELEGRAM_CHAT_ID:
        return False
    try:
        with open(filepath, 'rb') as photo:
            await bot.send_photo(chat_id=TELEGRAM_CHAT_ID, photo=photo, caption=caption)
        return True
    except Exception as e:
        print(f"[Telegram Notifier] Photo send failed: {e}")
        return False


# =============================================
# PUBLIC API — Call these from anywhere in Alfred
# =============================================

def send_alert(text: str) -> bool:
    """
    Send a text notification to the user's phone via Telegram.
    Safe to call from any thread. Returns True on success.
    """
    try:
        print(f"[Telegram Notifier] Pushing alert: {text[:60]}...")
        return _run_async(_send_message_async(text))
    except Exception as e:
        print(f"[Telegram Notifier] Alert failed: {e}")
        return False


def send_photo_alert(filepath: str, caption: str = "") -> bool:
    """
    Send a photo with optional caption to the user's phone via Telegram.
    Safe to call from any thread. Returns True on success.
    """
    if not os.path.exists(filepath):
        print(f"[Telegram Notifier] File not found: {filepath}")
        return False
    try:
        print(f"[Telegram Notifier] Pushing photo: {filepath}")
        return _run_async(_send_photo_async(filepath, caption))
    except Exception as e:
        print(f"[Telegram Notifier] Photo alert failed: {e}")
        return False


def is_available() -> bool:
    """Check if the Telegram notifier is properly configured."""
    return bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID and not TELEGRAM_BOT_TOKEN.startswith("your_"))
