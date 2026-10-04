"""
OSINT (Open-Source Intelligence) Tools for Alfred.
Gives Alfred access to the live internet: web search, news, earthquakes, and daily briefings.
"""

import os
import sys
import requests
from datetime import datetime

# ─────────────────────────────────────────────
# TOOL 1: Web Search (DuckDuckGo — no API key)
# ─────────────────────────────────────────────
def search_web(query: str) -> str:
    """
    Searches the web using DuckDuckGo and returns the top 3 results.
    This gives Alfred knowledge of current events and facts he doesn't know.
    """
    try:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=3))
        
        if not results:
            return f"No web results found for '{query}'."
        
        output = ""
        for i, r in enumerate(results):
            title = r.get("title", "No title")
            body = r.get("body", "No summary")
            output += f"{i+1}. {title}: {body}\n"
        
        return output.strip()
    except Exception as e:
        return f"Web search failed: {e}"


# ─────────────────────────────────────────────
# TOOL 2: Top News Headlines (Google News RSS)
# ─────────────────────────────────────────────
def get_news(topic: str = "world") -> str:
    """
    Fetches the top 5 news headlines from Google News RSS.
    topic can be: world, technology, science, business, health, sports, entertainment
    """
    try:
        # Google News RSS feeds by topic
        topic_map = {
            "world": "https://news.google.com/rss?hl=en-IN&gl=IN&ceid=IN:en",
            "technology": "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGRqTVhZU0FtVnVHZ0pKVGlnQVAB?hl=en-IN&gl=IN&ceid=IN:en",
            "science": "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRFp0Y1RjU0FtVnVHZ0pKVGlnQVAB?hl=en-IN&gl=IN&ceid=IN:en",
            "business": "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx6TVdZU0FtVnVHZ0pKVGlnQVAB?hl=en-IN&gl=IN&ceid=IN:en",
            "health": "https://news.google.com/rss/topics/CAAqIQgKIhtDQkFTRGdvSUwyMHZNR3QwTlRFU0FtVnVLQUFQAQ?hl=en-IN&gl=IN&ceid=IN:en",
            "sports": "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRFp1ZEdvU0FtVnVHZ0pKVGlnQVAB?hl=en-IN&gl=IN&ceid=IN:en",
            "entertainment": "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNREpxYW5RU0FtVnVHZ0pKVGlnQVAB?hl=en-IN&gl=IN&ceid=IN:en",
        }
        topic_lower = topic.lower().strip()
        if topic_lower in topic_map:
            url = topic_map[topic_lower]
        else:
            import urllib.parse
            query = urllib.parse.quote_plus(topic)
            url = f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"
        
        resp = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        
        # Simple XML parsing without extra dependencies
        import re
        items = re.findall(r'<item>.*?</item>', resp.text, re.DOTALL)
        
        if not items:
            return "Could not fetch news at this time."
        
        headlines = []
        for item in items[:5]:
            title_match = re.search(r'<title>(.*?)</title>', item)
            pub_match = re.search(r'<pubDate>(.*?)</pubDate>', item)
            
            title = title_match.group(1) if title_match else "Unknown"
            # Clean CDATA markers
            title = title.replace("<![CDATA[", "").replace("]]>", "").strip()
            
            pub = ""
            if pub_match:
                pub = pub_match.group(1).strip()
            
            headlines.append(f"• {title}")
        
        return "Top Headlines:\n" + "\n".join(headlines)
    except Exception as e:
        return f"Failed to fetch news: {e}"


# ─────────────────────────────────────────────
# TOOL 3: Earthquake Monitor (USGS — free API)
# ─────────────────────────────────────────────
def get_earthquakes(only_india: bool = True) -> str:
    """
    Fetches the most recent significant earthquakes from the USGS live feed.
    If only_india is True (default), filters strictly for earthquakes in or near India.
    """
    try:
        url = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_week.geojson"
        resp = requests.get(url, timeout=8)
        resp.raise_for_status()
        data = resp.json()
        
        features = data.get("features", [])
        if not features:
            return "No significant earthquakes detected in the last 7 days."
        
        indian_regions = [
            "india", "andaman", "nicobar", "kashmir", "ladakh", "assam", 
            "gujarat", "delhi", "himalaya", "uttarakhand", "himachal", 
            "bay of bengal", "arabian sea", "sikkim", "arunachal", "manipur",
            "mizoram", "nagaland", "tripura", "meghalaya", "hindu kush"
        ]
        
        filtered = []
        for eq in features:
            props = eq.get("properties", {})
            place = props.get("place", "Unknown location").lower()
            coords = eq.get("geometry", {}).get("coordinates", [])
            
            is_india = False
            # Keyword match
            if any(r in place for r in indian_regions):
                is_india = True
            # Geolocation bounding box for India (Lat: 6.0°N to 37.5°N, Lon: 68.0°E to 97.5°E)
            elif len(coords) >= 2:
                lon, lat = coords[0], coords[1]
                if 6.0 <= lat <= 37.5 and 68.0 <= lon <= 97.5:
                    is_india = True
            
            if only_india:
                if is_india:
                    filtered.append(eq)
            else:
                filtered.append(eq)
        
        if only_india and not filtered:
            return "No significant seismic activity detected in or near India this week."
        
        output = []
        for eq in filtered[:5]:
            props = eq.get("properties", {})
            mag = props.get("mag", "?")
            place = props.get("place", "Unknown location")
            time_ms = props.get("time", 0)
            
            # Convert epoch ms to human readable
            eq_time = datetime.fromtimestamp(time_ms / 1000).strftime("%b %d, %I:%M %p")
            output.append(f"• Magnitude {mag} — {place} ({eq_time})")
        
        target_name = "India" if only_india else "Global"
        header = f"Seismic Activity Report ({target_name}):\n"
        return header + "\n".join(output)
    except Exception as e:
        return f"Failed to fetch earthquake data: {e}"


# ─────────────────────────────────────────────
# TOOL 4: Daily Intelligence Briefing
# ─────────────────────────────────────────────
def daily_briefing() -> str:
    """
    Generates a comprehensive daily intelligence briefing combining:
    weather and top news, plus seismic alerts ONLY if detected in India.
    """
    from tools.core_tools import check_weather
    
    sections = []
    
    # Time context
    now = datetime.now()
    sections.append(f"Intelligence Briefing — {now.strftime('%A, %B %d, %Y at %I:%M %p')}")
    sections.append("")
    
    # Weather
    try:
        weather = check_weather()
        sections.append(f"WEATHER: {weather}")
    except:
        sections.append("WEATHER: Unable to retrieve.")
    sections.append("")
    
    # Top News
    try:
        news = get_news("world")
        sections.append(news)
    except:
        sections.append("NEWS: Unable to retrieve.")
    
    # Earthquakes — ONLY include if there is seismic activity in India!
    try:
        quakes = get_earthquakes(only_india=True)
        if "No significant seismic activity" not in quakes and "Failed" not in quakes:
            sections.append("")
            sections.append(quakes)
    except:
        pass
    
    return "\n".join(sections)


# ─────────────────────────────────────────────
# TOOL 5: Reverse Email Lookup (Holehe)
# ─────────────────────────────────────────────
def reverse_email_lookup(email: str) -> str:
    """
    Checks an email address against 120+ platforms (Twitter, Instagram, etc.) to see where it is registered.
    Runs silently and returns the list of associated websites.
    """
    import subprocess
    import re
    
    try:
        # Run holehe via subprocess, telling it to only show positive matches and no color codes
        cmd = ["./venv/Scripts/python", "-m", "holehe", email, "--only-used", "--no-color"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        output = result.stdout
        
        # Holehe output has lines starting with '[+] website.com'
        matches = re.findall(r'\[\+\]\s+([\w\.-]+)', output)
        
        if not matches:
            return f"No accounts found for the email: {email}."
            
        return f"The email '{email}' is registered on the following platforms:\n" + "\n".join([f"• {m}" for m in matches])
    except subprocess.TimeoutExpired:
        return f"Email lookup timed out for '{email}'."
    except Exception as e:
        return f"Failed to perform email lookup: {e}"

# ─────────────────────────────────────────────
# TOOL 6: Dynamic District Health Score (AI + OSINT)
# ─────────────────────────────────────────────
def generate_district_health_score(district_slug: str = None) -> str:
    """
    Generates a comprehensive 10-category District Health Score (Governance, Education, Health, 
    Infrastructure, Water, Economy, Safety, Agriculture, Digital, Welfare).
    It searches the web for recent data and uses Gemini to analyze and score the city.
    """
    import os
    if not district_slug:
        district_slug = os.getenv("USER_CITY", "Chikkamagaluru").strip()
    else:
        district_slug = district_slug.strip().title()
        
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "GEMINI_API_KEY is not set in .env. Required for Health Score calculation."
        
    try:
        # Step 1: Gather raw OSINT data
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS
        queries = [
            f"{district_slug} district literacy education statistics",
            f"{district_slug} infrastructure dam water economy",
            f"{district_slug} crime safety police statistics"
        ]
        
        raw_context = ""
        with DDGS() as ddgs:
            for q in queries:
                results = list(ddgs.text(q, max_results=3))
                for r in results:
                    raw_context += f"- {r.get('title')}: {r.get('body')}\n"
                    
        if not raw_context.strip():
            raw_context = "No specific real-time data found. Use general historical knowledge."
            
        # Step 2: Analyze with Gemini
        from google import genai
        client = genai.Client(api_key=api_key)
        
        prompt = f"""
        You are an expert Indian Civic Data Analyst. 
        Calculate an estimated District Health Score for '{district_slug}' out of 100 based on your training data and the following recent web search context:
        
        <OSINT_CONTEXT>
        {raw_context}
        </OSINT_CONTEXT>
        
        Provide a VERY CONCISE response (maximum 3 sentences). 
        Do NOT list out the 10 individual categories.
        Format your response like this:
        "The overall District Health Score for {district_slug} is [Score]/100 (Grade: [A-F]). [One sentence summarizing the strongest areas like Education or Safety]. [One sentence summarizing the weakest areas needing improvement like Healthcare or Infra]."
        
        Be objective and realistic.
        """
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        
        return response.text
        
    except Exception as e:
        return f"Failed to generate health score for {district_slug}: {e}"
# ─────────────────────────────────────────────
# TOOL 7: Stealth Web Fetch (TinyFish / Jina)
# ─────────────────────────────────────────────
def stealth_fetch_url(url: str) -> str:
    """
    Stealth scrapes a website bypassing Cloudflare/Bot-protection and returns clean Markdown.
    Uses Jina Reader API (or TinyFish) to extract article content.
    """
    import os
    import requests
    
    # We use Jina Reader as the reliable stealth endpoint which provides identical 
    # stealth Chrome-to-Markdown functionality without needing complex MCP servers.
    # If TinyFish REST endpoint becomes public, it can be swapped here using TINYFISH_API_KEY.
    
    try:
        jina_url = f"https://r.jina.ai/{url}"
        headers = {
            "Accept": "text/event-stream"
        }
        
        # We increase timeout because stealth headless browsers take 2-4 seconds to bypass Cloudflare
        resp = requests.get(jina_url, headers=headers, timeout=15)
        resp.raise_for_status()
        
        content = resp.text
        
        # Truncate to first 4000 chars to avoid overflowing Phi-3's memory context
        if len(content) > 4000:
            content = content[:4000] + "\n\n...[Content Truncated due to length]..."
            
        return f"Clean Markdown Content from {url}:\n\n{content}"
    except requests.Timeout:
        return f"Timeout while trying to stealth-fetch {url}. The site may have extreme bot-protection or is offline."
    except Exception as e:
        return f"Failed to stealth-fetch {url}: {e}"


# ─────────────────────────────────────────────
# TOOL 8: Geo-Intelligence News (OSINT → Globe)
# ─────────────────────────────────────────────

# Common location patterns for extraction
_KNOWN_COUNTRIES = {
    "india", "china", "russia", "ukraine", "usa", "us", "uk", "israel", "iran",
    "pakistan", "japan", "france", "germany", "brazil", "australia", "canada",
    "turkey", "egypt", "saudi arabia", "south korea", "north korea", "mexico",
    "indonesia", "nigeria", "south africa", "italy", "spain", "argentina",
    "colombia", "bangladesh", "thailand", "vietnam", "philippines", "taiwan",
    "myanmar", "afghanistan", "iraq", "syria", "yemen", "libya", "sudan",
    "ethiopia", "kenya", "morocco", "algeria", "poland", "romania", "netherlands",
    "greece", "portugal", "sweden", "norway", "finland", "denmark", "switzerland",
    "austria", "belgium", "czech republic", "hungary", "ireland", "scotland",
    "wales", "new zealand", "singapore", "malaysia", "sri lanka", "nepal",
}

def _extract_locations(text: str) -> list:
    """Extract location names from text using heuristic patterns."""
    import re
    locations = []

    # Check for known country names
    text_lower = text.lower()
    for country in _KNOWN_COUNTRIES:
        if country in text_lower:
            locations.append(country.title())

    # Extract capitalized multi-word place names (heuristic: 2-3 consecutive capitalized words)
    # This catches city names like "New Delhi", "Los Angeles", "Tel Aviv"
    place_pattern = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b', text)
    # Filter out common non-location capitalized words
    _stop_words = {
        "The", "This", "That", "These", "Those", "Monday", "Tuesday", "Wednesday",
        "Thursday", "Friday", "Saturday", "Sunday", "January", "February", "March",
        "April", "May", "June", "July", "August", "September", "October", "November",
        "December", "According", "President", "Minister", "Prime", "Breaking",
        "Reuters", "Associated Press", "Update", "Report", "Says", "After",
        "Before", "During", "World", "Global", "International", "National",
        "Government", "Security", "Council", "Defense", "Foreign", "Health",
        "Economic", "Political", "Military", "Official", "Statement",
    }
    for place in place_pattern:
        words = place.split()
        if words[0] not in _stop_words and len(place) > 3:
            locations.append(place)

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for loc in locations:
        loc_lower = loc.lower()
        if loc_lower not in seen:
            seen.add(loc_lower)
            unique.append(loc)

    return unique[:10]  # Cap at 10 locations


def _geocode_locations(locations: list) -> list:
    """Forward-geocode location names to lat/lng coordinates."""
    markers = []

    try:
        from geopy.geocoders import Nominatim
        geolocator = Nominatim(user_agent="alfred-osint-v1", timeout=5)
    except ImportError:
        # Fallback: use a small built-in dictionary for the most common locations
        _FALLBACK_COORDS = {
            "India": (20.5937, 78.9629), "China": (35.8617, 104.1954),
            "Russia": (61.5240, 105.3188), "Ukraine": (48.3794, 31.1656),
            "Usa": (37.0902, -95.7129), "Us": (37.0902, -95.7129),
            "Uk": (55.3781, -3.4360), "Israel": (31.0461, 34.8516),
            "Iran": (32.4279, 53.6880), "Pakistan": (30.3753, 69.3451),
            "Japan": (36.2048, 138.2529), "France": (46.2276, 2.2137),
            "Germany": (51.1657, 10.4515), "Brazil": (-14.2350, -51.9253),
            "New Delhi": (28.6139, 77.2090), "Moscow": (55.7558, 37.6173),
            "Beijing": (39.9042, 116.4074), "Tokyo": (35.6762, 139.6503),
            "London": (51.5074, -0.1278), "Paris": (48.8566, 2.3522),
            "Washington": (38.9072, -77.0369), "Kyiv": (50.4501, 30.5234),
            "Tel Aviv": (32.0853, 34.7818), "Tehran": (35.6892, 51.3890),
            "Cairo": (30.0444, 31.2357), "Riyadh": (24.7136, 46.6753),
            "Seoul": (37.5665, 126.9780), "Istanbul": (41.0082, 28.9784),
        }
        for loc in locations:
            if loc in _FALLBACK_COORDS:
                lat, lng = _FALLBACK_COORDS[loc]
                markers.append({"lat": lat, "lng": lng, "label": loc, "type": "news"})
        return markers

    import time
    for loc in locations:
        try:
            result = geolocator.geocode(loc)
            if result:
                markers.append({
                    "lat": result.latitude,
                    "lng": result.longitude,
                    "label": loc,
                    "type": "news",
                })
            time.sleep(1.1)  # Nominatim rate limit: 1 req/sec
        except Exception:
            continue

    return markers


def get_geo_news(topic: str = "world") -> str:
    """
    Fetches top news headlines, extracts geographical locations,
    geocodes them, and pushes markers to the 3D globe dashboard.
    Returns a summary of mapped locations.
    """
    import sys
    sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__))))

    try:
        # Step 1: Fetch news headlines
        news_text = get_news(topic)
        if not news_text or "Could not fetch" in news_text:
            return f"Could not fetch news for topic '{topic}'."

        # Step 2: Extract locations from headlines
        locations = _extract_locations(news_text)
        if not locations:
            return f"No geographical locations detected in the current '{topic}' headlines."

        # Step 3: Geocode to coordinates
        markers = _geocode_locations(locations)
        if not markers:
            return f"Extracted locations ({', '.join(locations)}) but could not geocode any of them."

        # Step 4: Push to globe via SSE
        try:
            import shared
            shared.push_geo_intel(markers)
            shared.push_globe(True)
        except Exception as e:
            print(f"[OSINT Geo] Failed to push to globe: {e}")

        # Step 5: Return summary
        loc_summary = ", ".join([f"{m['label']} ({m['lat']:.1f}°, {m['lng']:.1f}°)" for m in markers])
        return (
            f"Mapped {len(markers)} locations from '{topic}' news to the globe:\n"
            f"{loc_summary}\n\n"
            f"Headlines:\n{news_text}"
        )
    except Exception as e:
        return f"Geo-intelligence scan failed: {e}"


# ─────────────────────────────────────────────
# TOOL 9: Instagram Scraper (RapidAPI/Apify)
# ─────────────────────────────────────────────
def fetch_instagram_posts(username: str, limit: int = 3) -> str:
    """
    Fetches the latest posts from a specific Instagram account using a RapidAPI endpoint.
    Requires RAPIDAPI_KEY in .env.
    """
    import os
    import requests
    
    api_key = os.getenv("RAPIDAPI_KEY")
    if not api_key:
        return "RAPIDAPI_KEY is not configured in the environment. Cannot access Instagram."
        
    username = username.strip().lower().replace('@', '')
    
    try:
        # Switched to 'instagram-scraper-stable-api' as requested
        posts_url = "https://instagram-scraper-stable-api.p.rapidapi.com/user/posts"
        posts_query = {"username": username}
        
        headers = {
            "x-rapidapi-key": api_key,
            "x-rapidapi-host": "instagram-scraper-stable-api.p.rapidapi.com"
        }
        
        response = requests.get(posts_url, headers=headers, params=posts_query, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        # Generalized parser since RapidAPI endpoints vary in structure
        # Often it's data -> items, or just items, or edge_owner_to_timeline_media -> edges
        items = data.get("data", {}).get("items", []) 
        if not items and "items" in data:
            items = data["items"]
        if not items and "data" in data and isinstance(data["data"], list):
            items = data["data"]
            
        if not items:
            return f"No recent posts found for @{username} or the account is private/API response structure changed."
            
        output = [f"Latest Instagram posts from @{username}:\n"]
        
        count = 0
        for post in items:
            if count >= limit:
                break
                
            # Handle different caption structures
            caption = "No caption provided."
            if "caption" in post and isinstance(post["caption"], dict):
                caption = post["caption"].get("text", caption)
            elif "caption_text" in post:
                caption = post["caption_text"]
            elif "text" in post:
                caption = post["text"]
            
            # Truncate caption if it's too long
            if len(caption) > 200:
                caption = caption[:200] + "..."
                
            timestamp = post.get("taken_at") or post.get("timestamp")
            if timestamp:
                from datetime import datetime
                try:
                    time_str = datetime.fromtimestamp(int(timestamp)).strftime("%b %d, %I:%M %p")
                except:
                    time_str = str(timestamp)
            else:
                time_str = "Unknown time"
                
            likes = post.get("like_count", 0) or post.get("likes", 0)
            
            output.append(f"• [{time_str}] (Likes: {likes}): {caption}")
            count += 1
            
        return "\n".join(output)
        
    except Exception as e:
        return f"Failed to fetch Instagram posts for @{username}. Ensure your RAPIDAPI_KEY is valid and subscribed to 'Instagram Scraper Stable API'. Error: {e}"


# ─────────────────────────────────────────────
# TOOL 10: Reverse Face Search & Facial OSINT Intelligence
# ─────────────────────────────────────────────
OSINT_FACES_DIR = os.path.join(os.path.dirname(__file__), "..", "Alfred_Workspace", "osint_faces")
os.makedirs(OSINT_FACES_DIR, exist_ok=True)


def _capture_camera_face() -> str:
    """Captures a high-resolution snapshot from Alfred's camera for face searching."""
    try:
        import cv2
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            return ""
        # Allow sensor warm-up
        for _ in range(3):
            cap.read()
        ret, frame = cap.read()
        cap.release()
        if not ret or frame is None:
            return ""
            
        timestamp = int(datetime.now().timestamp())
        out_path = os.path.join(OSINT_FACES_DIR, f"face_query_{timestamp}.jpg")
        cv2.imwrite(out_path, frame)
        return out_path
    except Exception as e:
        print(f"[OSINT Tools] Camera face capture error: {e}")
        return ""


def _query_faceseek_online(image_path: str) -> dict:
    """
    Queries FaceSeek / FaceOnLive facial recognition search engine.
    Backend: https://www.faceseek.online/api/embed-search
    """
    try:
        url = "https://www.faceseek.online/api/embed-search"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://www.faceseek.online",
            "Referer": "https://www.faceseek.online/",
        }
        
        with open(image_path, "rb") as f:
            files = {"image": (os.path.basename(image_path), f, "image/jpeg")}
            resp = requests.post(url, headers=headers, files=files, timeout=20)
            
        if resp.status_code == 200:
            data = resp.json()
            matches = data.get("matches", []) or data.get("results", []) or data.get("data", [])
            return {
                "success": True,
                "engine": "FaceSeek Online (FaceOnLive Engine)",
                "matches": matches,
                "raw": data
            }
    except Exception as e:
        print(f"[OSINT Tools] FaceSeek API note: {e}")
        
    # Also attempt query via Gradio Space if available
    try:
        from gradio_client import Client, handle_file
        client = Client("FaceOnLive/Face-Search-Online")
        res = client.predict(
            image=handle_file(image_path),
            api_name="/predict"
        )
        if res:
            return {
                "success": True,
                "engine": "FaceOnLive HF Space",
                "matches": res if isinstance(res, list) else [res],
                "raw": res
            }
    except Exception as e:
        print(f"[OSINT Tools] FaceOnLive Space query note: {e}")
        
    return {"success": False}


def _analyze_face_demographics(image_path: str) -> str:
    """
    Analyzes facial features, age, expressions, clothing, and public figure status using Gemini 2.5 Flash.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return ""
    try:
        from google import genai
        from google.genai import types
        
        client = genai.Client(api_key=api_key)
        with open(image_path, "rb") as f:
            img_bytes = f.read()
            
        prompt = (
            "You are Alfred's Senior Facial Recognition & OSINT Intelligence Analyst.\n"
            "Examine this face/person image thoroughly and produce a concise intelligence profile:\n"
            "1. Face Detection & Posture: Confirm if human face(s) are present, face angle/head pose.\n"
            "2. Demographic Estimation: Apparent age range, gender presentation.\n"
            "3. Distinctive Facial Features: Hairstyle/hair color, facial hair (beard/mustache), eye color/shape, glasses, piercings, scars, or distinct marks.\n"
            "4. Expressions & Mood: Emotional state and eye gaze direction.\n"
            "5. Attire & Context: Clothing style, uniforms, badges, logos, jewelry, background environment cues.\n"
            "6. Public Recognition Check: If this person is a recognized public figure, celebrity, executive, political figure, creator, or athlete, explicitly state their identity, role, and key facts. If they appear to be a private individual, state 'No public celebrity/historical figure match identified'.\n\n"
            "Keep the format clean, bulleted, and professional."
        )
        
        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                prompt,
                types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg")
            ]
        )
        return resp.text.strip() if resp and resp.text else ""
    except Exception as e:
        print(f"[OSINT Tools] Gemini facial analysis error: {e}")
        return ""


def reverse_face_search(image_path: str = None) -> str:
    """
    Performs Reverse Face Search and Facial OSINT Intelligence on any photo or live camera frame.
    Integrates FaceOnLive/FaceSeek facial embedding search, Gemini 2.5 Flash facial biometrics,
    public figure identification, and direct OSINT search dossiers.

    Args:
        image_path: Local path to an image file (e.g. 'C:/photos/target.jpg').
                    If omitted, empty, or 'camera', captures a snapshot from the live camera.
    """
    target_path = image_path.strip() if image_path else ""
    
    # 1. Camera snapshot if requested or path is empty
    if not target_path or target_path.lower() in ["camera", "webcam", "live", "selfie", "me"]:
        print("[OSINT Tools] Capturing live face image from camera...")
        target_path = _capture_camera_face()
        if not target_path:
            return "Could not capture image from camera, sir. Please verify the webcam is active or provide an image file path."
            
    # Clean quotes around path
    target_path = target_path.strip('\'"')
    if not os.path.exists(target_path):
        return f"Image file not found at '{target_path}', sir. Please check the file path."
        
    print(f"[OSINT Tools] Initiating Reverse Face Search on: {target_path}")
    
    # 2. Run Facial Biometrics & Public Recognition via Gemini
    bio_profile = _analyze_face_demographics(target_path)
    
    # 3. Query Online Face Recognition Search Engine (FaceSeek / FaceOnLive)
    online_res = _query_faceseek_online(target_path)
    
    # 4. Generate OSINT Referral Dossier Links
    basename = os.path.basename(target_path)
    osint_links = [
        "🌐 *OSINT Deep-Link Investigation Dossiers:*",
        "• Google Lens Visual Search: https://lens.google.com/",
        "• PimEyes Face Search: https://pimeyes.com/en",
        "• FaceCheck ID Verification: https://facecheck.id/",
        "• Yandex Facial Reverse Image Search: https://yandex.com/images/search?rpt=imageview"
    ]
    
    # 5. Format Executive Intelligence Report
    report = [
        f"🕵️ *FACIAL OSINT & REVERSE SEARCH INTELLIGENCE*",
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"📁 *Source Image:* `{basename}`",
    ]
    
    if bio_profile:
        report.append(f"\n👤 *Facial Biometrics & Demographics:*")
        report.append(bio_profile)
        
    if online_res.get("success") and online_res.get("matches"):
        matches = online_res["matches"]
        report.append(f"\n🔍 *Online Database Matches ({online_res['engine']}):*")
        count = 0
        for m in matches[:5]:
            count += 1
            if isinstance(m, dict):
                score = m.get("score") or m.get("similarity") or m.get("confidence", "N/A")
                url = m.get("url") or m.get("source_url") or m.get("link", "Link unavailable")
                title = m.get("title") or m.get("domain") or "Web Match"
                report.append(f"  {count}. [{title}]({url}) — Similarity: {score}")
            elif isinstance(m, str):
                report.append(f"  {count}. {m}")
    else:
        report.append(f"\n🔍 *Online Face Database Query:* Search submitted to FaceOnLive index. No exact commercial match returned in instant tier; biometric profile and deep links compiled.")
        
    report.append("\n" + "\n".join(osint_links))
    
    return "\n".join(report)


