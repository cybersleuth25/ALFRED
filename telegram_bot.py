import os
import sys
import asyncio
import tempfile
import time
from dotenv import load_dotenv
import telegram
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import llm_engine

# Ensure parent directory is in path for tool imports
sys.path.append(os.path.join(os.path.dirname(__file__)))

load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_ALLOWED_USER_ID = os.getenv("TELEGRAM_ALLOWED_USER_ID")
GEMINI_TELEGRAM_KEY = os.getenv("GEMINI_TELEGRAM_API_KEY", os.getenv("GEMINI_API_KEY", ""))


# =============================================
# SECURITY
# =============================================

import functools

def _is_authorized(update: Update) -> bool:
    """Check if the message sender is the authorized user."""
    user_id = str(update.effective_user.id)
    if user_id != TELEGRAM_ALLOWED_USER_ID:
        print(f"\n[Telegram Bot] ⚠️ UNAUTHORIZED attempt from User ID: {user_id}")
        return False
    return True

def authorized_only(func):
    """Decorator to enforce user authorization for Telegram bot handlers."""
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if not _is_authorized(update):
            await update.message.reply_text("Unauthorized access.")
            return
        return await func(update, context, *args, **kwargs)
    return wrapper


# =============================================
# COMMAND HANDLERS
# =============================================

@authorized_only
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /start command."""
    await update.message.reply_text(
        "Good day, sir. Alfred Protocol Mobile Link established.\n\n"
        "Available commands:\n"
        "/status — System health check\n"
        "/screenshot — Capture your PC screen\n"
        "\nOr simply send a text message to control Alfred remotely.\n"
        "You can also send a photo for AI image analysis."
    )


@authorized_only
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Returns a full system health report."""
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')

    try:
        import psutil
        import memory_engine

        # CPU & RAM
        cpu = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        # Battery
        battery = psutil.sensors_battery()
        if battery:
            batt_str = f"🔋 {battery.percent}% {'⚡ Charging' if battery.power_plugged else '🔌 On battery'}"
        else:
            batt_str = "🖥️ Desktop (no battery)"

        # Focus Mode
        try:
            import study_mentor
            omega_str = "🔴 ACTIVE" if study_mentor.is_active() else "⚪ Inactive"
        except Exception:
            omega_str = "⚪ Unknown"

        # Memory stats
        mem_count = memory_engine.get_memory_count()
        pending_tasks = len(memory_engine.get_pending_tasks())

        report = (
            f"📊 *ALFRED SYSTEM STATUS*\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"💻 CPU: {cpu}%\n"
            f"🧠 RAM: {mem.percent}% ({round(mem.used / (1024**3), 1)}/{round(mem.total / (1024**3), 1)} GB)\n"
            f"💾 Disk: {disk.percent}% ({round(disk.used / (1024**3), 0)}/{round(disk.total / (1024**3), 0)} GB)\n"
            f"{batt_str}\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 Focus Mode: {omega_str}\n"
            f"🧩 Semantic Memories: {mem_count}\n"
            f"📋 Pending Tasks: {pending_tasks}\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"✅ Alfred is online and operational."
        )

        await update.message.reply_text(report, parse_mode='Markdown')

    except Exception as e:
        await update.message.reply_text(f"Error generating status: {e}")


@authorized_only
async def screenshot_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Takes a screenshot of the PC and sends it to the user."""
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='upload_photo')

    try:
        from tools.system_tools import take_screenshot
        result = take_screenshot()

        # Extract filepath from the result string
        if "Screenshot saved to" in result:
            filepath = result.replace("Screenshot saved to ", "").strip()
            if os.path.exists(filepath):
                with open(filepath, 'rb') as photo:
                    await update.message.reply_photo(
                        photo=photo,
                        caption="📸 Your PC screen right now, sir."
                    )
                return

        await update.message.reply_text(f"Screenshot result: {result}")

    except Exception as e:
        await update.message.reply_text(f"Error taking screenshot: {e}")


# =============================================
# MESSAGE HANDLERS
# =============================================

async def keep_typing(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Periodically sends typing action to keep the indicator alive."""
    try:
        while True:
            await context.bot.send_chat_action(chat_id=chat_id, action='typing')
            await asyncio.sleep(4)
    except asyncio.CancelledError:
        pass


@authorized_only
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Routes text messages through Alfred's brain."""
    user_text = update.message.text
    print(f"\n[Telegram Bot] Received remote command: '{user_text}'")

    chat_id = update.effective_chat.id
    typing_task = asyncio.create_task(keep_typing(context, chat_id))

    try:
        # Run synchronous LLM call in a separate thread to prevent event loop blocking
        response = await asyncio.to_thread(llm_engine.generate_response, user_text)
        
        # Telegram has a 4096 char limit per message
        if len(response) > 4000:
            # Smart chunking by double newlines
            chunks = response.split("\n\n")
            current_msg = ""
            for chunk in chunks:
                if len(current_msg) + len(chunk) + 2 > 4000:
                    if current_msg:
                        await update.message.reply_text(current_msg)
                    current_msg = chunk
                else:
                    current_msg += ("\n\n" + chunk if current_msg else chunk)
            if current_msg:
                await update.message.reply_text(current_msg)
        else:
            await update.message.reply_text(response)
    except Exception as e:
        error_msg = f"Error processing command remotely: {e}"
        print(f"[Telegram Bot] {error_msg}")
        await update.message.reply_text(error_msg)
    finally:
        typing_task.cancel()


@authorized_only
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives a photo, analyzes it using Gemini Vision, and responds."""
    chat_id = update.effective_chat.id
    typing_task = asyncio.create_task(keep_typing(context, chat_id))

    try:
        # Download the highest resolution photo
        photo = update.message.photo[-1]  # Last element = highest res
        file = await context.bot.get_file(photo.file_id)

        # Save to temp file safely
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp_file:
            tmp_path = tmp_file.name
            
        await file.download_to_drive(tmp_path)

        # Get the caption (user's question about the image) or use default
        caption = update.message.caption or "Describe this image in detail. What do you see?"

        # Analyze with Gemini Vision
        if not GEMINI_TELEGRAM_KEY:
            await update.message.reply_text(
                "Image analysis requires a Gemini API key. "
                "Please add GEMINI_TELEGRAM_API_KEY to your .env file."
            )
            return

        from google import genai
        from google.genai import types

        client = genai.Client(api_key=GEMINI_TELEGRAM_KEY)

        with open(tmp_path, 'rb') as f:
            image_bytes = f.read()

        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                caption,
                types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")
            ]
        )

        analysis = response.text.strip()
        print(f"[Telegram Bot] Image analysis: {analysis[:100]}...")

        if len(analysis) > 4000:
            chunks = analysis.split("\n\n")
            current_msg = ""
            for chunk in chunks:
                if len(current_msg) + len(chunk) + 2 > 4000:
                    if current_msg:
                        await update.message.reply_text(current_msg)
                    current_msg = chunk
                else:
                    current_msg += ("\n\n" + chunk if current_msg else chunk)
            if current_msg:
                await update.message.reply_text(current_msg)
        else:
            await update.message.reply_text(f"🔍 *Image Analysis:*\n\n{analysis}", parse_mode='Markdown')

    except Exception as e:
        error_msg = f"Image analysis failed: {e}"
        print(f"[Telegram Bot] {error_msg}")
        await update.message.reply_text(error_msg)
    finally:
        typing_task.cancel()
        # Clean up temp file
        if 'tmp_path' in locals():
            try:
                os.remove(tmp_path)
            except Exception:
                pass


# =============================================
# BOT STARTUP
# =============================================

def start_telegram_bot_loop():
    """Starts the Telegram bot in a dedicated thread."""
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN.startswith("your_"):
        print("[Telegram Bot] Skipped: No valid token found in .env.")
        return

    if not TELEGRAM_ALLOWED_USER_ID:
        print("[Telegram Bot] Warning: TELEGRAM_ALLOWED_USER_ID is missing from .env. The bot will reject all interactions.")

    print("[Telegram Bot] Initializing background listener...")

    # We must create a new event loop since this runs in a background thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Command Handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("screenshot", screenshot_command))

    # Message Handlers
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Start polling with bounded retry loop
    max_retries = 5
    for attempt in range(max_retries):
        try:
            print(f"[Telegram Bot] Starting polling (attempt {attempt + 1}/{max_retries})...")
            app.run_polling(
                allowed_updates=Update.ALL_TYPES,
                close_loop=False,
                drop_pending_updates=True,
            )
            break  # Exits if stopped gracefully
        except telegram.error.Conflict:
            wait = min(30, 10 * (attempt + 1))
            print(f"\n[Telegram Bot] Conflict — another instance may be running. Retry in {wait}s...")
            time.sleep(wait)
        except Exception as e:
            print(f"\n[Telegram Bot] Network or polling error: {e}. Restarting in 5s...")
            time.sleep(5)
    else:
        print("[Telegram Bot] Failed after max retries. Another bot instance is likely still running.")
