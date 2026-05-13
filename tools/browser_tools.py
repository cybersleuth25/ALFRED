"""
Browser Tab Control via Chrome DevTools Protocol (CDP).
Supports multiple Chromium-based browsers simultaneously (Edge, Chrome, Brave).
Each browser must be launched with --remote-debugging-port=XXXX.

Hardened with retry logic, fuzzy tab matching, and proper error handling.
"""

import requests
import subprocess
import json
import time

# Port assignments for each browser
BROWSER_PORTS = {
    "Edge": 9222,
    "Chrome": 9223,
    "Brave": 9224,
}


def _get_tabs(port: int, retries: int = 2) -> list:
    """Fetch all open tabs from a browser's CDP endpoint with retry logic."""
    for attempt in range(retries):
        try:
            resp = requests.get(f"http://127.0.0.1:{port}/json", timeout=2)
            if resp.status_code == 200:
                return [t for t in resp.json() if t.get("type") == "page"]
        except requests.ConnectionError:
            if attempt < retries - 1:
                time.sleep(0.5)
        except Exception:
            pass
    return []


def _get_all_tabs() -> list:
    """Fetch tabs from ALL running browsers and tag them with browser name."""
    all_tabs = []
    for browser_name, port in BROWSER_PORTS.items():
        tabs = _get_tabs(port)
        for tab in tabs:
            tab["_browser"] = browser_name
            tab["_port"] = port
            all_tabs.append(tab)
    return all_tabs


def _fuzzy_match_tab(tabs: list, query: str) -> dict | None:
    """
    Find the best matching tab using fuzzy scoring.
    Scores: exact match > starts-with > contains > partial word match.
    Returns the best match or None.
    """
    query_lower = query.lower().strip()
    if not query_lower:
        return None
    
    scored = []
    for tab in tabs:
        title = tab.get("title", "").lower()
        url = tab.get("url", "").lower()
        score = 0
        
        # Exact title match
        if title == query_lower:
            score = 100
        # Title starts with query
        elif title.startswith(query_lower):
            score = 80
        # Query is contained in title
        elif query_lower in title:
            score = 60
        # Query is contained in URL
        elif query_lower in url:
            score = 40
        # Partial word matching (e.g., "you" matches "YouTube")
        else:
            query_words = query_lower.split()
            matches = sum(1 for w in query_words if w in title or w in url)
            if matches > 0:
                score = 20 + (matches / len(query_words)) * 20
        
        if score > 0:
            scored.append((score, tab))
    
    if not scored:
        return None
    
    # Return highest scoring tab
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1]


def list_browser_tabs() -> str:
    """Lists all open tabs across all running browsers."""
    all_tabs = _get_all_tabs()
    if not all_tabs:
        return "No browser tabs detected. Make sure your browser was launched with debugging enabled, or say 'open Chrome' or 'open Edge' to let me launch it correctly."

    output = ""
    current_browser = None
    for idx, tab in enumerate(all_tabs, 1):
        if tab["_browser"] != current_browser:
            current_browser = tab["_browser"]
            output += f"\n{current_browser}:\n"
        title = tab.get("title", "Untitled")[:60]
        output += f"  {idx}. {title}\n"

    return output.strip()


def close_browser_tab(title: str) -> str:
    """Closes a browser tab by matching its title (fuzzy match, best match wins)."""
    all_tabs = _get_all_tabs()
    target = _fuzzy_match_tab(all_tabs, title)
    
    if not target:
        return f"No tab found matching '{title}'. Use 'list tabs' to see all open tabs."

    try:
        tab_id = target.get("id")
        port = target["_port"]
        resp = requests.get(f"http://127.0.0.1:{port}/json/close/{tab_id}", timeout=3)
        if resp.status_code == 200:
            return f"Closed tab: '{target.get('title', 'Unknown')}' in {target['_browser']}."
        return f"Close command sent for '{target.get('title')}' but got status {resp.status_code}."
    except Exception as e:
        return f"Error closing tab: {e}"


def switch_browser_tab(title: str) -> str:
    """Activates/focuses a browser tab by matching its title (fuzzy match)."""
    all_tabs = _get_all_tabs()
    target = _fuzzy_match_tab(all_tabs, title)
    
    if not target:
        return f"No tab found matching '{title}'."

    try:
        tab_id = target.get("id")
        port = target["_port"]
        resp = requests.get(f"http://127.0.0.1:{port}/json/activate/{tab_id}", timeout=3)
        if resp.status_code == 200:
            return f"Switched to tab: '{target.get('title', 'Unknown')}' in {target['_browser']}."
        return f"Switch command sent for '{target.get('title')}' but got status {resp.status_code}."
    except Exception as e:
        return f"Error switching tab: {e}"


def open_browser_tab(url: str) -> str:
    """Opens a new tab in the first available browser with debugging enabled."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    # Auto-prepend https if no protocol specified
    if not url.startswith("http"):
        url = f"https://{url}"

    # Probe all browser ports concurrently to find the first available one
    def _try_open(browser_name, port):
        try:
            resp = requests.get(f"http://127.0.0.1:{port}/json/version", timeout=2)
            if resp.status_code == 200:
                new_resp = requests.get(f"http://127.0.0.1:{port}/json/new?{url}", timeout=3)
                if new_resp.status_code == 200:
                    return f"Opened {url} in {browser_name}."
                return f"Sent open command to {browser_name} (status: {new_resp.status_code})."
        except Exception:
            pass
        return None

    with ThreadPoolExecutor(max_workers=len(BROWSER_PORTS)) as pool:
        futures = {pool.submit(_try_open, name, port): name for name, port in BROWSER_PORTS.items()}
        for future in as_completed(futures):
            result = future.result()
            if result:
                return result

    # Fallback: open in default browser via webbrowser module
    import webbrowser
    webbrowser.open(url)
    return f"Opened {url} in default browser (no debug-enabled browser found)."


def read_browser_tab(title: str = "") -> str:
    """Reads the visible text content of a browser tab. If no title given, reads the active tab."""
    all_tabs = _get_all_tabs()
    if not all_tabs:
        return "No browser tabs detected."

    target_tab = None
    if title:
        target_tab = _fuzzy_match_tab(all_tabs, title)
    else:
        # Use the first tab as a rough "active" proxy
        target_tab = all_tabs[0] if all_tabs else None

    if not target_tab:
        return f"No tab found matching '{title}'."

    try:
        ws_url = target_tab.get("webSocketDebuggerUrl")
        if not ws_url:
            return f"Cannot read tab '{target_tab.get('title')}' — no WebSocket URL available."

        port = target_tab["_port"]
        tab_id = target_tab["id"]

        try:
            import websocket
        except ImportError:
            return (
                f"Tab '{target_tab.get('title')}' found, but the 'websocket-client' package is needed to read content. "
                f"Install it with: pip install websocket-client\n"
                f"Title: {target_tab.get('title')}, URL: {target_tab.get('url')}"
            )

        ws = websocket.create_connection(ws_url, timeout=5)
        ws.send(json.dumps({
            "id": 1,
            "method": "Runtime.evaluate",
            "params": {"expression": "document.body.innerText.substring(0, 2000)"}
        }))
        result = json.loads(ws.recv())
        ws.close()

        text = result.get("result", {}).get("result", {}).get("value", "")
        if text:
            # Truncate to prevent LLM context overflow
            truncated = text[:800]
            suffix = "... (truncated)" if len(text) > 800 else ""
            return f"Content from '{target_tab.get('title', 'Unknown')}':\n{truncated}{suffix}"
        return f"Tab '{target_tab.get('title')}' appears to be empty or loading."
    except Exception as e:
        return f"Error reading tab: {e}"
