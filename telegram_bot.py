import os
import sys
import asyncio
import tempfile
import time
from dotenv import load_dotenv
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

def _is_authorized(update: Update) -> bool:
    """Check if the message sender is the authorized user."""
    user_id = str(update.effective_user.id)
    if user_id != TELEGRAM_ALLOWED_USER_ID:
        print(f"\n[Telegram Bot] ⚠️ UNAUTHORIZED attempt from User ID: {user_id}")
        return False
    return True


# =============================================
# COMMAND HANDLERS
# =============================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /start command."""
    if not _is_authorized(update):
        await update.message.reply_text(
            f"Unauthorized. Your Telegram ID is {update.effective_user.id}. "
            "Please add this to the .env file if you are the authorized user."
        )
        return
    await update.message.reply_text(
        "Good day, sir. Alfred Protocol Mobile Link established.\n\n"
        "Available commands:\n"
        "/status — System health check\n"
        "/screenshot — Capture your PC screen\n"
        "\nOr simply send a text message to control Alfred remotely.\n"
        "You can also send a photo for AI image analysis."
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Returns a full system health report."""
    if not _is_authorized(update):
        await update.message.reply_text("Unauthorized access.")
        return

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

        # Protocol Omega
        try:
            import study_mentor
            omega_str = "🔴 ACTIVE" if study_mentor.is_active() else "⚪ Inactive"
        except:
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
            f"🎯 Protocol Omega: {omega_str}\n"
            f"🧩 Semantic Memories: {mem_count}\n"
            f"📋 Pending Tasks: {pending_tasks}\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"✅ Alfred is online and operational."
        )

        await update.message.reply_text(report, parse_mode='Markdown')

    except Exception as e:
        await update.message.reply_text(f"Error generating status: {e}")


async def screenshot_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Takes a screenshot of the PC and sends it to the user."""
    if not _is_authorized(update):
        await update.message.reply_text("Unauthorized access.")
        return

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

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Routes text messages through Alfred's brain."""
    if not _is_authorized(update):
        await update.message.reply_text(
            f"Unauthorized access. Your Telegram ID is {update.effective_user.id}."
        )
        return

    user_text = update.message.text
    print(f"\n[Telegram Bot] Received remote command: '{user_text}'")

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')

    try:
        response = llm_engine.generate_response(user_text)
        # Telegram has a 4096 char limit per message
        if len(response) > 4000:
            # Split into chunks
            for i in range(0, len(response), 4000):
                await update.message.reply_text(response[i:i+4000])
        else:
            await update.message.reply_text(response)
    except Exception as e:
        error_msg = f"Error processing command remotely: {e}"
        print(f"[Telegram Bot] {error_msg}")
        await update.message.reply_text(error_msg)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives a photo, analyzes it using Gemini Vision, and responds."""
    if not _is_authorized(update):
        await update.message.reply_text("Unauthorized access.")
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')

    try:
        # Download the highest resolution photo
        photo = update.message.photo[-1]  # Last element = highest res
        file = await context.bot.get_file(photo.file_id)

        # Save to temp file
        tmp_path = os.path.join(tempfile.gettempdir(), f"alfred_telegram_{photo.file_id}.jpg")
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
            for i in range(0, len(analysis), 4000):
                await update.message.reply_text(analysis[i:i+4000])
        else:
            await update.message.reply_text(f"🔍 *Image Analysis:*\n\n{analysis}", parse_mode='Markdown')

        # Clean up temp file
        try:
            os.remove(tmp_path)
        except:
            pass

    except Exception as e:
        error_msg = f"Image analysis failed: {e}"
        print(f"[Telegram Bot] {error_msg}")
        await update.message.reply_text(error_msg)


# =============================================
# BOT STARTUP
# =============================================

def start_telegram_bot_loop():
    """Starts the Telegram bot in a dedicated thread."""
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN.startswith("your_"):
        print("[Telegram Bot] Skipped: No valid token found in .env.")
        return

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

    # Start polling with robust retry loop
    while True:
        try:
            print("[Telegram Bot] Starting polling...")
            app.run_polling(allowed_updates=Update.ALL_TYPES, close_loop=False)
            break # Exits if stopped gracefully
        except Exception as e:
            print(f"\n[Telegram Bot] Network or polling error: {e}. Restarting in 5s...")
            time.sleep(5)
