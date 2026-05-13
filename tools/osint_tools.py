"""
OSINT (Open-Source Intelligence) Tools for Alfred.
Gives Alfred access to the live internet: web search, news, earthquakes, and daily briefings.
"""

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
def get_earthquakes() -> str:
    """
    Fetches the most recent significant earthquakes from the USGS live feed.
    Returns the top 5 earthquakes from the last 7 days.
    """
    try:
        url = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_week.geojson"
        resp = requests.get(url, timeout=8)
        resp.raise_for_status()
        data = resp.json()
        
        features = data.get("features", [])
        if not features:
            return "No significant earthquakes detected in the last 7 days."
        
        output = []
        for eq in features[:5]:
            props = eq.get("properties", {})
            mag = props.get("mag", "?")
            place = props.get("place", "Unknown location")
            time_ms = props.get("time", 0)
            
            # Convert epoch ms to human readable
            eq_time = datetime.fromtimestamp(time_ms / 1000).strftime("%b %d, %I:%M %p")
            
            output.append(f"• Magnitude {mag} — {place} ({eq_time})")
        
        total = len(features)
        header = f"Seismic Activity Report ({total} quakes M4.5+ this week):\n"
        return header + "\n".join(output)
    except Exception as e:
        return f"Failed to fetch earthquake data: {e}"


# ─────────────────────────────────────────────
# TOOL 4: Daily Intelligence Briefing
# ─────────────────────────────────────────────
def daily_briefing() -> str:
    """
    Generates a comprehensive daily intelligence briefing combining:
    weather, top news, and seismic activity.
    """
    from tools.core_tools import check_weather
    
    sections = []
    
    # Time context
    now = datetime.now()
    greeting_time = "morning" if now.hour < 12 else "afternoon" if now.hour < 17 else "evening"
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
    sections.append("")
    
    # Earthquakes
    try:
        quakes = get_earthquakes()
        sections.append(quakes)
    except:
        sections.append("SEISMIC: Unable to retrieve.")
    
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
