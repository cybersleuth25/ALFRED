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
import media_control
import voice_engine

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
        "🛡️ *ALFRED PROTOCOL — MOBILE REMOTE ACTIVE*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🎙️ *Voice Notes:* Send any voice message! Alfred will transcribe, process with tools, and send back a voice note.\n\n"
        "💻 *Screen & Vision:*\n"
        "• `/screen [question]` — Inspect PC screen + AI diagnosis\n"
        "• `/screenshot` — Quick snapshot of desktop\n"
        "• Send any photo with caption for visual analysis\n\n"
        "🎵 *Media Remote Control:*\n"
        "• `/play <song>` — Play Spotify/YouTube on PC\n"
        "• `/pause` — Pause playback\n"
        "• `/resume` — Resume playback\n"
        "• `/next` or `/skip` — Next track\n"
        "• `/prev` — Previous track\n"
        "• `/mute` — Mute/unmute sound\n"
        "• `/volup` / `/voldn` — Volume up/down\n\n"
        "🛠️ *Developer Co-Pilot:*\n"
        "• `/git [project|all|list]` — Live repo status across projects\n"
        "• `/scan [project]` — Scan codebase for leaked keys/secrets\n"
        "• `/clean [project]` — Clean junk caches & reclaim disk space\n"
        "• `/run <cmd>` — Run safe terminal command on PC\n"
        "• `/meeting [start|stop]` — Record meeting & write minutes\n\n"
        "🏛️ *Chief of Staff & Calendar:*\n"
        "• `/agenda` or `/calendar` — Schedule, conflicts & focus slots\n"
        "• `/email` or `/inbox` — Priority inbox triage\n"
        "• `/dossier` — Complete morning executive dossier\n"
        "• `/schedule <title> at <time>` — Book event on Google/Samsung Cal\n\n"
        "📈 *Market Intelligence & Chronos:*\n"
        "• `/stock <symbol>` — Live quote for Indian (NSE/BSE) or global stocks\n"
        "• `/forecast <symbol> [days]` — Amazon Chronos price prediction\n\n"
        "🕵️ *Facial OSINT & Face Search:*\n"
        "• `/facesearch` — Search face via camera or reply to photo\n"
        "• Send photo with caption 'face search' or 'who is this'\n\n"
        "⚙️ *System:*\n"
        "• `/status` — System health & active focus",

        parse_mode='Markdown'
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


@authorized_only
async def play_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Plays a song or toggles playback on PC."""
    query = " ".join(context.args).strip() if context.args else ""
    if query:
        await update.message.reply_text(f"Searching and playing '{query}' on PC...")
        res = await asyncio.to_thread(media_control.play_song, query)
        await update.message.reply_text(f"🎵 {res}")
    else:
        res = media_control.play_pause()
        await update.message.reply_text(f"▶️ {res}")


@authorized_only
async def pause_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pauses media playback on PC."""
    res = media_control.play_pause()
    await update.message.reply_text(f"⏸️ {res}")


@authorized_only
async def resume_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Resumes media playback on PC."""
    res = media_control.play_pause()
    await update.message.reply_text(f"▶️ {res}")


@authorized_only
async def next_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Skips to next track on PC."""
    res = media_control.next_track()
    await update.message.reply_text(f"⏭️ {res}")


@authorized_only
async def prev_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Skips to previous track on PC."""
    res = media_control.previous_track()
    await update.message.reply_text(f"⏮️ {res}")


@authorized_only
async def mute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggles audio mute on PC."""
    res = media_control.toggle_mute()
    await update.message.reply_text(f"🔇 {res}")


@authorized_only
async def volup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Raises system volume on PC."""
    res = media_control.volume_up()
    await update.message.reply_text(f"🔊 {res}")


@authorized_only
async def voldn_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lowers system volume on PC."""
    res = media_control.volume_down()
    await update.message.reply_text(f"🔉 {res}")


@authorized_only
async def screen_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Captures PC screen and analyzes it with Screen Co-Pilot."""
    query = " ".join(context.args).strip() if context.args else "What is on my screen?"
    chat_id = update.effective_chat.id
    typing_task = asyncio.create_task(keep_typing(context, chat_id))
    try:
        import screen_copilot
        res = await asyncio.to_thread(screen_copilot.analyze_screen, query)
        jpeg_bytes = await asyncio.to_thread(screen_copilot.capture_screen_jpeg_bytes)
        analysis_text = res.get("analysis", "No analysis returned.")
        win_info = res.get("window", {})
        header = f"🖥️ *Active Window:* `{win_info.get('title', 'Desktop')}` ({win_info.get('process', 'Unknown')})\n\n"
        full_caption = header + analysis_text
        if len(full_caption) <= 1024:
            await update.message.reply_photo(photo=jpeg_bytes, caption=full_caption, parse_mode='Markdown')
        else:
            await update.message.reply_photo(photo=jpeg_bytes, caption=header[:1024], parse_mode='Markdown')
            await update.message.reply_text(analysis_text)
    except Exception as e:
        await update.message.reply_text(f"Screen co-pilot error: {e}")
    finally:
        typing_task.cancel()


@authorized_only
async def git_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Returns live git repository status from PC. Supports /git <project>, /git all, /git list."""
    target = " ".join(context.args).strip() if context.args else ""
    from tools import developer_tools
    res = await asyncio.to_thread(developer_tools.git_status_diff, target)
    await update.message.reply_text(res)


@authorized_only
async def scan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Scans code files on PC for leaked secrets or API tokens. Supports /scan <project>."""
    target = " ".join(context.args).strip() if context.args else ""
    lbl = f" for '{target}'" if target else ""
    await update.message.reply_text(f"🔍 Scanning codebase{lbl} for exposed keys & secrets...")
    from tools import developer_tools
    res = await asyncio.to_thread(developer_tools.scan_leaked_secrets, target)
    await update.message.reply_text(res)


@authorized_only
async def clean_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cleans temporary build caches to free disk space. Supports /clean <project>."""
    target = " ".join(context.args).strip() if context.args else ""
    from tools import developer_tools
    res = await asyncio.to_thread(developer_tools.clean_dev_workspace, target)
    await update.message.reply_text(res)



@authorized_only
async def run_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Runs a terminal command safely on the PC and returns output."""
    cmd = " ".join(context.args).strip() if context.args else ""
    if not cmd:
        await update.message.reply_text("Usage: `/run <command>`\nExample: `/run git branch -a` or `/run python --version`")
        return
    await update.message.reply_text(f"⚡ Running on PC: `{cmd}`...")
    from tools import developer_tools
    res = await asyncio.to_thread(developer_tools.run_terminal_command, cmd)
    await update.message.reply_text(res)


@authorized_only
async def meeting_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Controls meeting recording mode."""
    act = context.args[0].lower().strip() if context.args else "status"
    title = " ".join(context.args[1:]).strip() if len(context.args) > 1 else ""
    from tools import developer_tools
    res = await asyncio.to_thread(developer_tools.meeting_notetaker, act, title)
    await update.message.reply_text(res)


@authorized_only
async def agenda_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Returns today's calendar schedule, conflicts, and focus blocks."""
    date_arg = " ".join(context.args).strip() if context.args else "today"
    import chief_of_staff
    res = await asyncio.to_thread(chief_of_staff.get_quick_agenda, date_arg)
    await update.message.reply_text(res)


@authorized_only
async def email_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Returns inbox triage and unread priority emails."""
    from tools import email_tools
    res = await asyncio.to_thread(email_tools.triage_inbox, 6)
    await update.message.reply_text(res)


@authorized_only
async def dossier_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generates the full Chief of Staff Morning Executive Dossier."""
    await update.message.reply_text("🏛️ Synthesizing your Chief of Staff Executive Dossier...")
    import chief_of_staff
    res = await asyncio.to_thread(chief_of_staff.get_daily_executive_dossier)
    await update.message.reply_text(res)


@authorized_only
async def schedule_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Quickly books an event on Google & Samsung Calendar."""
    raw = " ".join(context.args).strip() if context.args else ""
    if not raw:
        await update.message.reply_text("Usage: `/schedule <event title> at <time>`\nExample: `/schedule Team Sync at 3pm tomorrow`")
        return
    
    if " at " in raw.lower():
        parts = re.split(r'\s+at\s+', raw, flags=re.IGNORECASE, maxsplit=1)
        title = parts[0].strip()
        time_str = parts[1].strip()
    else:
        title = raw
        time_str = "in 1 hour"

    from tools import calendar_tools
    res = await asyncio.to_thread(calendar_tools.create_calendar_event, title, time_str)
    await update.message.reply_text(res)


@authorized_only
async def stock_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetches real-time market quote for Indian (NSE/BSE) or global stocks."""
    chat_id = update.effective_chat.id
    typing_task = asyncio.create_task(keep_typing(context, chat_id))
    try:
        from tools import market_tools
        symbol = " ".join(context.args).strip() if context.args else "NIFTY"
        res = await asyncio.to_thread(market_tools.get_stock_quote, symbol)
        await update.message.reply_text(res)
    except Exception as e:
        await update.message.reply_text(f"Error fetching stock quote: {e}")
    finally:
        typing_task.cancel()


@authorized_only
async def forecast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Runs Amazon Chronos market forecast & technical indicators."""
    chat_id = update.effective_chat.id
    typing_task = asyncio.create_task(keep_typing(context, chat_id))
    try:
        from tools import market_tools
        args = context.args or []
        symbol = "NIFTY"
        days = 14
        if args:
            if args[-1].isdigit():
                days = int(args[-1])
                symbol = " ".join(args[:-1]).strip() or "NIFTY"
            else:
                symbol = " ".join(args).strip()
        await update.message.reply_text(f"📊 Computing Amazon Chronos forecast for *{symbol}* ({days}-day horizon)...", parse_mode='Markdown')
        res = await asyncio.to_thread(market_tools.forecast_stock, symbol, days)
        await update.message.reply_text(res)
    except Exception as e:
        await update.message.reply_text(f"Error computing stock forecast: {e}")
    finally:
        typing_task.cancel()


@authorized_only
async def facesearch_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Performs Reverse Face Search and Facial OSINT."""
    chat_id = update.effective_chat.id
    typing_task = asyncio.create_task(keep_typing(context, chat_id))
    tmp_path = None
    try:
        from tools import osint_tools
        
        reply = update.message.reply_to_message
        if reply and reply.photo:
            photo = reply.photo[-1]
            file = await context.bot.get_file(photo.file_id)
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp_file:
                tmp_path = tmp_file.name
            await file.download_to_drive(tmp_path)
            target_img = tmp_path
        elif context.args:
            target_img = " ".join(context.args).strip()
        else:
            target_img = "camera"
            
        await update.message.reply_text("🕵️ Initiating Reverse Face Search & OSINT analysis...")
        res = await asyncio.to_thread(osint_tools.reverse_face_search, target_img)
        await update.message.reply_text(res, parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"Face search failed: {e}")
    finally:
        typing_task.cancel()
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass


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
async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives voice note, transcribes via Gemini, processes with Alfred brain, replies with voice note."""
    chat_id = update.effective_chat.id
    await context.bot.send_chat_action(chat_id=chat_id, action='record_voice')
    typing_task = asyncio.create_task(keep_typing(context, chat_id))

    tmp_voice_path = None
    tmp_reply_voice = None
    try:
        voice_obj = update.message.voice or update.message.audio
        if not voice_obj:
            await update.message.reply_text("Could not extract audio from message.")
            return

        voice_file = await context.bot.get_file(voice_obj.file_id)
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp_file:
            tmp_voice_path = tmp_file.name
        await voice_file.download_to_drive(tmp_voice_path)

        with open(tmp_voice_path, 'rb') as f:
            audio_bytes = f.read()

        from google import genai
        from google.genai import types

        api_key = GEMINI_TELEGRAM_KEY or os.getenv("GEMINI_API_KEY")
        if not api_key:
            await update.message.reply_text("Error: GEMINI_API_KEY is required to process voice notes.")
            return

        client = genai.Client(api_key=api_key)
        transcribe_prompt = (
            "Transcribe this voice message accurately and verbatim in the original language spoken "
            "(English, Hindi, or Hinglish). Do not add any commentary, filler, notes, or quotes. "
            "Output ONLY the pure transcription text."
        )

        tr_resp = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                transcribe_prompt,
                types.Part.from_bytes(data=audio_bytes, mime_type="audio/ogg")
            ]
        )
        user_text = tr_resp.text.strip()
        print(f"\n[Telegram Bot] 🎙️ Transcribed voice: \"{user_text}\"")

        if not user_text:
            await update.message.reply_text("Could not detect any speech in your voice note, sir.")
            return

        # Process command through Alfred's brain / tools
        response = await asyncio.to_thread(llm_engine.generate_response, user_text)

        # Synthesize voice response
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as reply_file:
            tmp_reply_voice = reply_file.name

        clean_for_speech = response
        if len(clean_for_speech) > 600:
            clean_for_speech = clean_for_speech[:600] + "..."

        await voice_engine.synthesize_to_file_async(clean_for_speech, tmp_reply_voice)

        caption_text = f"🎙️ *You:* \"{user_text}\"\n\n💬 *Alfred:*\n{response}"
        if os.path.exists(tmp_reply_voice) and os.path.getsize(tmp_reply_voice) > 1000:
            with open(tmp_reply_voice, 'rb') as voice_reply:
                if len(caption_text) <= 1024:
                    await update.message.reply_voice(voice=voice_reply, caption=caption_text, parse_mode='Markdown')
                else:
                    await update.message.reply_voice(voice=voice_reply, caption=f"🎙️ \"{user_text}\"")
                    await update.message.reply_text(response)
        else:
            await update.message.reply_text(caption_text, parse_mode='Markdown')

    except Exception as e:
        error_msg = f"Voice note processing failed: {e}"
        print(f"[Telegram Bot] {error_msg}")
        await update.message.reply_text(error_msg)
    finally:
        typing_task.cancel()
        for p in [tmp_voice_path, tmp_reply_voice]:
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
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

        # Check if user requested reverse face search on this photo
        caption_lower = caption.lower()
        if any(term in caption_lower for term in ['facesearch', 'face search', 'who is this', 'identify face', 'find person', 'reverse face']):
            from tools import osint_tools
            print("[Telegram Bot] Auto-routing photo to Reverse Face Search OSINT...")
            face_report = await asyncio.to_thread(osint_tools.reverse_face_search, tmp_path)
            await update.message.reply_text(face_report, parse_mode='Markdown')
            return

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

_lock_socket = None

def _acquire_bot_lock() -> bool:
    """Ensures only a single local process polls Telegram to prevent 409 Conflict spam."""
    global _lock_socket
    try:
        import socket
        _lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        _lock_socket.bind(('127.0.0.1', 19891))
        return True
    except Exception:
        return False


def start_telegram_bot_loop():
    """Starts the Telegram bot in a dedicated thread."""
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN.startswith("your_"):
        print("[Telegram Bot] Skipped: No valid token found in .env.")
        return

    if not _acquire_bot_lock():
        print("[Telegram Bot] Mobile link already running in another active process. Skipping duplicate poll.")
        return

    if not TELEGRAM_ALLOWED_USER_ID:
        print("[Telegram Bot] Warning: TELEGRAM_ALLOWED_USER_ID is missing from .env. The bot will reject all interactions.")

    print("[Telegram Bot] Initializing background listener...")

    # We must create a new event loop since this runs in a background thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    from telegram.request import HTTPXRequest
    http_req = HTTPXRequest(
        connection_pool_size=8,
        read_timeout=30.0,
        write_timeout=30.0,
        connect_timeout=30.0,
        pool_timeout=30.0,
    )
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).request(http_req).build()

    # Command Handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", start_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("screenshot", screenshot_command))
    app.add_handler(CommandHandler("screen", screen_command))

    # Media Remote Controls
    app.add_handler(CommandHandler("play", play_command))
    app.add_handler(CommandHandler("pause", pause_command))
    app.add_handler(CommandHandler("resume", resume_command))
    app.add_handler(CommandHandler("next", next_command))
    app.add_handler(CommandHandler("skip", next_command))
    app.add_handler(CommandHandler("prev", prev_command))
    app.add_handler(CommandHandler("mute", mute_command))
    app.add_handler(CommandHandler("volup", volup_command))
    app.add_handler(CommandHandler("voldn", voldn_command))

    # Developer Co-Pilot Remote Controls
    app.add_handler(CommandHandler("git", git_command))
    app.add_handler(CommandHandler("scan", scan_command))
    app.add_handler(CommandHandler("clean", clean_command))
    app.add_handler(CommandHandler("run", run_command_handler))
    app.add_handler(CommandHandler("meeting", meeting_command))

    # Chief of Staff & Calendar Remote Controls
    app.add_handler(CommandHandler("agenda", agenda_command))
    app.add_handler(CommandHandler("calendar", agenda_command))
    app.add_handler(CommandHandler("email", email_command))
    app.add_handler(CommandHandler("inbox", email_command))
    app.add_handler(CommandHandler("dossier", dossier_command))
    app.add_handler(CommandHandler("chief", dossier_command))
    app.add_handler(CommandHandler("schedule", schedule_command))

    # Market Intelligence & Chronos Predictions
    app.add_handler(CommandHandler("stock", stock_command))
    app.add_handler(CommandHandler("forecast", forecast_command))

    # Facial OSINT & Reverse Face Search
    app.add_handler(CommandHandler("facesearch", facesearch_command))


    # Message Handlers
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))
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
                bootstrap_retries=5,
                timeout=20,
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
