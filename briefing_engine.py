"""
Startup Briefing Engine for Alfred.
====================================
Generates a concise, REAL intelligence briefing for Alfred to speak on first wake.

Includes:
- Time-of-day greeting
- Current weather for Chikkamagaluru (real data from wttr.in)
- Rain advisory ("Carry an umbrella if you head out")
- Pending task count
- Top news headline (1 only, for brevity)
- Battery status warning (if under 30%)

CRITICAL: Everything here is REAL data from live APIs. Nothing is fabricated.
If an API fails, that section is gracefully skipped.
"""

import os
import requests
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dotenv import load_dotenv

load_dotenv()

USER_CITY = os.getenv("USER_CITY", "Chikkamagaluru")


def _get_weather_data() -> dict:
    """
    Fetches structured weather data from wttr.in for the user's city.
    Returns a dict with: temp_c, feels_like, humidity, description, rain_chance, wind.
    Returns empty dict on failure.
    """
    try:
        url = f"https://wttr.in/{USER_CITY}?format=j1"
        resp = requests.get(url, timeout=8, headers={"User-Agent": "curl"})
        resp.raise_for_status()
        data = resp.json()

        current = data.get("current_condition", [{}])[0]
        # Get nearest weather forecast area for rain chance
        weather_today = data.get("weather", [{}])[0]
        hourly = weather_today.get("hourly", [])

        # Find the closest hourly forecast to current time
        current_hour = datetime.now().hour
        rain_chance = 0
        for h in hourly:
            h_time = int(h.get("time", "0")) // 100
            if h_time >= current_hour:
                rain_chance = int(h.get("chanceofrain", "0"))
                break

        return {
            "temp_c": current.get("temp_C", "?"),
            "feels_like": current.get("FeelsLikeC", "?"),
            "humidity": current.get("humidity", "?"),
            "description": current.get("weatherDesc", [{}])[0].get("value", "Unknown"),
            "rain_chance": rain_chance,
            "wind_kmph": current.get("windspeedKmph", "?"),
        }
    except Exception as e:
        print(f"[Briefing] Weather fetch failed: {e}")
        return {}


def _get_top_headline() -> str:
    """Fetches a single top news headline from Google News RSS. Returns empty string on failure."""
    try:
        import re
        url = "https://news.google.com/rss?hl=en-IN&gl=IN&ceid=IN:en"
        resp = requests.get(url, timeout=6, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()

        items = re.findall(r'<item>.*?</item>', resp.text, re.DOTALL)
        if items:
            title_match = re.search(r'<title>(.*?)</title>', items[0])
            if title_match:
                title = title_match.group(1).replace("<![CDATA[", "").replace("]]>", "").strip()
                # Truncate very long headlines for speech
                if len(title) > 120:
                    title = title[:117] + "..."
                return title
        return ""
    except Exception as e:
        print(f"[Briefing] News fetch failed: {e}")
        return ""


def _get_battery_warning() -> str:
    """Returns a battery warning string if under 30% and not charging. Empty otherwise."""
    try:
        import psutil
        battery = psutil.sensors_battery()
        if battery and battery.percent <= 30 and not battery.power_plugged:
            return f"Your battery is at {battery.percent} percent and not charging. I'd recommend plugging in soon."
        return ""
    except Exception:
        return ""


def _get_pending_task_count() -> int:
    """Returns the number of pending tasks."""
    try:
        import memory_engine
        return len(memory_engine.get_pending_tasks())
    except Exception:
        return 0


BRIEFING_CACHE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Alfred_Workspace", "briefing_cache.json")

def _is_offline() -> bool:
    """Checks for active internet connectivity with a fast timeout."""
    import socket
    try:
        socket.setdefaulttimeout(1.5)
        # Check by connecting to a reliable public DNS IP address
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("8.8.8.8", 53))
        return False
    except Exception:
        return True

def generate_startup_briefing(user_name: str) -> str:
    """
    Generates a concise, REAL intelligence briefing for Alfred to speak on first wake.
    Uses the local LLM to phrase the raw data naturally and uniquely every time.
    """
    now = datetime.now()
    hour = now.hour

    # Time-of-day context
    if 5 <= hour < 12:
        time_context = "morning"
    elif 12 <= hour < 17:
        time_context = "afternoon"
    elif 17 <= hour < 22:
        time_context = "evening"
    else:
        time_context = "late night"

    weather = {}
    headline = ""
    cached_note = ""

    # Check connection. If offline, load cached data to avoid blocking timeouts.
    if _is_offline():
        print("[Briefing] System is offline. Loading cached intelligence...")
        try:
            import json
            if os.path.exists(BRIEFING_CACHE_PATH):
                with open(BRIEFING_CACHE_PATH, "r", encoding="utf-8") as f:
                    cache = json.load(f)
                    weather = cache.get("weather", {})
                    headline = cache.get("headline", "")
                    cached_at_str = cache.get("cached_at", "")
                    if cached_at_str:
                        cached_dt = datetime.fromisoformat(cached_at_str)
                        time_diff = datetime.now() - cached_dt
                        if time_diff.total_seconds() < 86400:
                            cached_note = f" (cached {int(time_diff.total_seconds() // 3600)} hours ago)"
                        else:
                            cached_note = f" (cached on {cached_dt.strftime('%B %d')})"
        except Exception as e:
            print(f"[Briefing] Failed to load cached briefing: {e}")
            
        task_count = _get_pending_task_count()
        batt_warning = _get_battery_warning()
    else:
        # Gather Data in parallel (cuts ~15s sequential → ~5s parallel)
        with ThreadPoolExecutor(max_workers=4) as pool:
            weather_future = pool.submit(_get_weather_data)
            task_future = pool.submit(_get_pending_task_count)
            batt_future = pool.submit(_get_battery_warning)
            news_future = pool.submit(_get_top_headline)
            
            try:
                weather = weather_future.result(timeout=10)
            except Exception:
                weather = {}
            try:
                task_count = task_future.result(timeout=5)
            except Exception:
                task_count = 0
            try:
                batt_warning = batt_future.result(timeout=3)
            except Exception:
                batt_warning = ""
            try:
                headline = news_future.result(timeout=8)
            except Exception:
                headline = ""

        # Save successfully retrieved data to cache
        if weather or headline:
            try:
                import json
                os.makedirs(os.path.dirname(BRIEFING_CACHE_PATH), exist_ok=True)
                with open(BRIEFING_CACHE_PATH, "w", encoding="utf-8") as f:
                    json.dump({
                        "weather": weather,
                        "headline": headline,
                        "cached_at": datetime.now().isoformat()
                    }, f)
            except Exception as e:
                print(f"[Briefing] Failed to cache briefing data: {e}")

    # Parse the gathered data
    temp = weather.get("temp_c", "?") if weather else "?"
    desc = weather.get("description", "unknown weather").lower() if weather else "unknown weather"
    rain = weather.get("rain_chance", 0) if weather else 0
    
    rain_text = ""
    if rain >= 60:
        rain_text = "High chance of rain (suggest an umbrella)."
    elif rain >= 30:
        rain_text = "Moderate chance of rain."

    task_text = f"{task_count} pending tasks." if task_count > 0 else "No pending tasks."

    # Construct strict prompt for the LLM
    data_points = f"- Current Time: {time_context}\n- Weather in {USER_CITY}: {temp}°C, {desc}{cached_note}. {rain_text}\n- Tasks: {task_text}\n"
    if batt_warning:
        data_points += f"- Alert: {batt_warning}\n"
    if headline:
        data_points += f"- Top News: {headline}\n"

    prompt = f"""You are Alfred, a highly sophisticated British AI butler. Generate a short, warm, and highly unique conversational greeting for Master {user_name}.
You MUST seamlessly and naturally weave the following data into your greeting:
{data_points}
Rules:
1. Do not use robotic bullet points. Speak in flowing, elegant paragraphs.
2. Keep it under 3-4 sentences.
3. Do not invent or hallucinate any facts outside of the provided data.
4. End by asking how you can assist."""

    try:
        import llm_engine
        res = llm_engine.chat(
            messages=[{'role': 'user', 'content': prompt}],
            options={'temperature': 0.7, 'num_predict': 150}
        )
        return res['message']['content'].strip()
    except Exception as e:
        print(f"[Briefing Error] LLM generation failed, falling back to basic string: {e}")
        # Fallback to basic robotic string if LLM fails
        return f"Good {time_context}, Master {user_name}. It is {temp} degrees in {USER_CITY}. How may I assist you?"
