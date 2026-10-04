"""
Live Screen Co-Pilot for JARVIS / ALFRED.
========================================
Multimodal visual intelligence on the active desktop screen using Gemini 2.5 Flash / Groq.
Features:
- Instant pure-Windows GDI BitBlt desktop screen capture (<15ms).
- Active foreground window detection (window title, process name, PID).
- Multimodal visual reasoning tailored to the active persona (Alfred, Jarvis, Friday).
- Specialized modes: general inspection, code debugging, diagram explanation, article reading.
"""

import os
import io
import time
import ctypes
from ctypes import wintypes
import psutil
from PIL import Image
from dotenv import load_dotenv

import shared
import persona_engine

load_dotenv()

# --- Win32 GDI Screen Capture ---
user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

# Set DPI awareness so full resolution is captured
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-monitor DPI aware
except Exception:
    try:
        user32.SetProcessDPIAware()
    except Exception:
        pass


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ('biSize', wintypes.DWORD),
        ('biWidth', wintypes.LONG),
        ('biHeight', wintypes.LONG),
        ('biPlanes', wintypes.WORD),
        ('biBitCount', wintypes.WORD),
        ('biCompression', wintypes.DWORD),
        ('biSizeImage', wintypes.DWORD),
        ('biXPelsPerMeter', wintypes.LONG),
        ('biYPelsPerMeter', wintypes.LONG),
        ('biClrUsed', wintypes.DWORD),
        ('biClrImportant', wintypes.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [
        ('bmiHeader', BITMAPINFOHEADER),
        ('bmiColors', wintypes.DWORD * 3)
    ]


def get_active_window_info() -> dict:
    """Returns title and process name of the current foreground window."""
    try:
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return {"title": "Desktop", "process": "explorer.exe", "pid": 0}
        
        # Get window text
        length = user32.GetWindowTextLengthW(hwnd)
        buff = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buff, length + 1)
        title = buff.value.strip() or "Untitled Window"

        # Get process info
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        process_name = "Unknown"
        try:
            p = psutil.Process(pid.value)
            process_name = p.name()
        except Exception:
            pass

        return {"title": title, "process": process_name, "pid": pid.value}
    except Exception as e:
        return {"title": "Desktop", "process": "Unknown", "pid": 0, "error": str(e)}


def capture_screen_pil() -> Image.Image:
    """Captures the primary monitor using pure Windows GDI BitBlt (<15ms)."""
    hdesktop = user32.GetDesktopWindow()
    width = user32.GetSystemMetrics(0)   # SM_CXSCREEN
    height = user32.GetSystemMetrics(1)  # SM_CYSCREEN

    desktop_dc = user32.GetDC(hdesktop)
    mem_dc = gdi32.CreateCompatibleDC(desktop_dc)
    bitmap = gdi32.CreateCompatibleBitmap(desktop_dc, width, height)
    old_bitmap = gdi32.SelectObject(mem_dc, bitmap)

    # SRCCOPY = 0x00CC0020
    gdi32.BitBlt(mem_dc, 0, 0, width, height, desktop_dc, 0, 0, 0x00CC0020)

    bmi = BITMAPINFO()
    bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.bmiHeader.biWidth = width
    bmi.bmiHeader.biHeight = -height  # Top-down DIB
    bmi.bmiHeader.biPlanes = 1
    bmi.bmiHeader.biBitCount = 32
    bmi.bmiHeader.biCompression = 0   # BI_RGB

    buffer_size = width * height * 4
    buffer = (ctypes.c_char * buffer_size)()
    gdi32.GetDIBits(mem_dc, bitmap, 0, height, buffer, ctypes.byref(bmi), 0)

    # Cleanup GDI handles
    gdi32.SelectObject(mem_dc, old_bitmap)
    gdi32.DeleteObject(bitmap)
    gdi32.DeleteDC(mem_dc)
    user32.ReleaseDC(hdesktop, desktop_dc)

    # BGRA to RGBA
    img = Image.frombuffer('RGBA', (width, height), buffer, 'raw', 'BGRA', 0, 1)
    return img.convert('RGB')


def capture_screen_jpeg_bytes(quality=80, max_dimension=1600) -> bytes:
    """Captures screen and compresses to optimized JPEG bytes for LLM vision inference."""
    img = capture_screen_pil()
    # Downscale slightly to speed up network upload & vision token processing
    if max(img.width, img.height) > max_dimension:
        ratio = max_dimension / max(img.width, img.height)
        new_size = (int(img.width * ratio), int(img.height * ratio))
        img = img.resize(new_size, Image.Resampling.LANCZOS)
    
    bio = io.BytesIO()
    img.save(bio, format="JPEG", quality=quality, optimize=True)
    return bio.getvalue()


# --- Multimodal Vision Engine ---

def _call_gemini_vision(jpeg_bytes: bytes, prompt: str, system_instruction: str) -> str:
    """Executes multimodal analysis with Google Gemini 2.5 Flash."""
    from google import genai
    from google.genai import types

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not configured in .env")

    client = genai.Client(api_key=api_key)
    
    contents = [
        types.Part.from_bytes(data=jpeg_bytes, mime_type="image/jpeg"),
        prompt
    ]
    
    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        temperature=0.2,
        max_output_tokens=1000
    )

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=contents,
        config=config
    )
    return response.text.strip()


def analyze_screen(user_query: str = "What is on my screen?", mode: str = "general") -> dict:
    """
    Main entry point for Screen Co-Pilot.
    Captures active screen and performs intelligent analysis.
    Returns:
        {
            "analysis": str,
            "window": dict,
            "timestamp": str,
            "success": bool
        }
    """
    start_time = time.time()
    win_info = get_active_window_info()
    persona = persona_engine.get_active_persona()

    # Persona-tailored system prompt
    base_instructions = (
        f"You are {persona.display_name}. {persona.personality_prompt} "
        f"You are directly observing the user's primary monitor. "
        f"The user is {persona.honorific}. "
        f"The active foreground window is '{win_info.get('title')}' running under '{win_info.get('process')}'. "
        f"Provide concise, razor-sharp, actionable observations in character ({persona.name}). "
        f"Never hallucinate UI elements that are not clearly visible. Keep explanations direct and spoken-friendly."
    )

    if mode == "debug" or any(w in user_query.lower() for w in ["debug", "error", "traceback", "fix"]):
        mode_prompt = (
            f"User request: '{user_query}'\n"
            "Analyze the code or terminal error visible on screen. "
            "1. Pinpoint the exact line or root cause of the error. "
            "2. Provide the exact code fix in 2-3 sentences."
        )
    elif mode == "diagram" or any(w in user_query.lower() for w in ["diagram", "chart", "architecture", "flowchart"]):
        mode_prompt = (
            f"User request: '{user_query}'\n"
            "Explain the architecture, diagram, or visual structure visible on screen clearly and hierarchically."
        )
    elif mode == "read" or any(w in user_query.lower() for w in ["read", "summarize", "article"]):
        mode_prompt = (
            f"User request: '{user_query}'\n"
            "Summarize the core takeaways of the document or webpage currently displayed on screen."
        )
    else:
        mode_prompt = (
            f"User request: '{user_query}'\n"
            "Inspect what the user is working on or looking at right now, and answer their query directly."
        )

    try:
        jpeg_bytes = capture_screen_jpeg_bytes()
        analysis = _call_gemini_vision(jpeg_bytes, mode_prompt, base_instructions)
        elapsed = round(time.time() - start_time, 2)
        
        return {
            "success": True,
            "analysis": analysis,
            "window": win_info,
            "elapsed_seconds": elapsed,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        print(f"[Screen Co-Pilot Error] {e}")
        return {
            "success": False,
            "analysis": f"I was unable to analyze your screen, {persona.honorific}. Error: {e}",
            "window": win_info,
            "elapsed_seconds": round(time.time() - start_time, 2),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }


if __name__ == "__main__":
    print("Testing Screen Co-Pilot...")
    info = get_active_window_info()
    print(f"Active window: {info}")
    res = analyze_screen("What is currently on my screen?")
    print("Result:\n", res["analysis"])
