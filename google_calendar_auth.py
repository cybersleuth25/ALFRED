"""
Google Calendar OAuth Setup for Alfred / JARVIS.
================================================
One-time script to authorize Alfred to access your Google & Samsung Calendar.

Usage:
    python google_calendar_auth.py

This will:
1. Load credentials from `credentials.json` or your `.env` (GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET).
2. Open your web browser to sign in to your Google Account.
3. Save the permanent offline refresh token to `token.json`.
4. Test the connection immediately by fetching your upcoming schedule.

BEFORE RUNNING:
1. Go to Google Cloud Console: https://console.cloud.google.com/
2. Create a new project (or select an existing one).
3. In "APIs & Services" -> "Library", enable "Google Calendar API".
4. In "OAuth consent screen":
   - Select User Type: External.
   - Fill in App Name (e.g. "Alfred Assistant") and your email.
   - Add your Gmail as a "Test User" under the Test Users tab.
5. In "Credentials" -> "Create Credentials" -> "OAuth client ID":
   - Application type: "Desktop app" (or "Web application" with http://127.0.0.1:8080/callback).
   - Click Create and download the JSON.
   - Rename it to `credentials.json` and save it in this project folder (`c:\\VS Code\\JARVIS\\credentials.json`).
   - (Alternatively, set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in your `.env` file).
"""

import os
import sys
import json
import webbrowser
import urllib.parse
from datetime import datetime, timedelta, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_PATH = os.path.join(BASE_DIR, "credentials.json")
TOKEN_PATH = os.path.join(BASE_DIR, "token.json")

SCOPES = ["https://www.googleapis.com/auth/calendar"]
REDIRECT_URI = "http://127.0.0.1:8080/callback"
PORT = 8080

_auth_code = None


class CallbackHandler(BaseHTTPRequestHandler):
    """Handles the OAuth2 callback from Google."""

    def do_GET(self):
        global _auth_code
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)

        if "code" in params:
            _auth_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"""
                <!DOCTYPE html>
                <html>
                <body style="background:#0a0a0a;color:#fff;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0">
                <div style="text-align:center;padding:40px;background:#141414;border-radius:12px;border:1px solid #222;max-width:480px;box-shadow:0 8px 32px rgba(0,0,0,0.5)">
                    <div style="font-size:48px;color:#3b82f6;margin-bottom:16px">&#10003;</div>
                    <h1 style="font-size:22px;margin:0 0 10px;font-weight:600">Google Calendar Connected</h1>
                    <p style="color:#aaa;font-size:14px;line-height:1.5;margin:0 0 20px">
                        JARVIS now has access to your schedule. Any events on your Samsung Calendar synced with Google are accessible. You may close this tab.
                    </p>
                </div>
                </body>
                </html>
            """)
        else:
            error = params.get("error", ["Unknown authorization error"])[0]
            _auth_code = None
            self.send_response(400)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(f"<html><body style='background:#111;color:#ff5555;font-family:sans-serif;padding:30px'><h2>Authorization Error</h2><p>{error}</p></body></html>".encode())

    def log_message(self, format, *args):
        pass  # Suppress console HTTP access logs


def _load_client_credentials():
    """Extracts client_id and client_secret from credentials.json or .env."""
    client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()

    if os.path.exists(CREDENTIALS_PATH):
        try:
            with open(CREDENTIALS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                info = data.get("installed") or data.get("web") or data
                client_id = info.get("client_id", client_id)
                client_secret = info.get("client_secret", client_secret)
        except Exception as e:
            print(f"[Notice] Could not parse credentials.json: {e}")

    return client_id, client_secret


def main():
    print("=" * 60)
    print("      ALFRED / JARVIS — Google Calendar Authorization")
    print("=" * 60)
    print()

    client_id, client_secret = _load_client_credentials()

    if not client_id or not client_secret:
        print("[!] Missing Google OAuth Credentials.")
        print()
        print("Please follow these steps to obtain credentials:")
        print(" 1. Visit: https://console.cloud.google.com/")
        print(" 2. Enable 'Google Calendar API' in APIs & Services.")
        print(" 3. Set OAuth Consent Screen -> External -> Add your Gmail as a Test User.")
        print(" 4. Create OAuth Client ID -> Type: Desktop app (or Web App with redirect http://127.0.0.1:8080/callback).")
        print(" 5. Download the JSON file and save it as: credentials.json in this folder:")
        print(f"    {CREDENTIALS_PATH}")
        print("    (OR set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env)")
        print()
        sys.exit(1)

    # First attempt: Try official google-auth-oauthlib if available
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        flow = None
        if os.path.exists(CREDENTIALS_PATH):
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
        else:
            client_config = {
                "installed": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [REDIRECT_URI]
                }
            }
            flow = InstalledAppFlow.from_client_config(client_config, SCOPES)

        print("[*] Launching browser for Google authentication...")
        creds = flow.run_local_server(port=PORT, prompt="consent", access_type="offline")

        with open(TOKEN_PATH, "w", encoding="utf-8") as f:
            f.write(creds.to_json())

        print(f"[✓] Authorization successful! Saved token to: {TOKEN_PATH}")
        _verify_connection(creds)
        return

    except ImportError:
        # Fallback to pure requests + built-in HTTPServer (no extra libraries required)
        pass
    except Exception as e:
        print(f"[Notice] Native OAuthlib failed ({e}). Using built-in local server flow...")

    # Fallback Custom OAuth Flow
    global _auth_code
    server = HTTPServer(('127.0.0.1', PORT), CallbackHandler)

    params = {
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
    }
    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)

    print("[*] Opening Google login in your default browser...")
    webbrowser.open(auth_url)
    print(f"[*] Waiting for authentication callback on {REDIRECT_URI}...")

    server.handle_request()

    if not _auth_code:
        print("[X] Failed to receive authorization code. Please try again.")
        sys.exit(1)

    print("[*] Exchanging authorization code for permanent tokens...")
    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "code": _auth_code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code"
    }

    resp = requests.post(token_url, data=data, timeout=15)
    if resp.status_code != 200:
        print(f"[X] Token exchange failed ({resp.status_code}): {resp.text}")
        sys.exit(1)

    token_data = resp.json()
    expires_in = token_data.get("expires_in", 3600)
    expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

    token_payload = {
        "token": token_data.get("access_token"),
        "refresh_token": token_data.get("refresh_token"),
        "token_uri": token_url,
        "client_id": client_id,
        "client_secret": client_secret,
        "scopes": SCOPES,
        "expiry": expiry.strftime("%Y-%m-%dT%H:%M:%SZ")
    }

    with open(TOKEN_PATH, "w", encoding="utf-8") as f:
        json.dump(token_payload, f, indent=2)

    print(f"[✓] Authorization successful! Token saved to: {TOKEN_PATH}")
    _verify_pure_requests(token_payload)


def _verify_connection(creds):
    """Verifies connection using googleapiclient."""
    try:
        from googleapiclient.discovery import build
        service = build('calendar', 'v3', credentials=creds, cache_discovery=False)
        events = service.events().list(calendarId='primary', maxResults=3).execute()
        print("[✓] Successfully verified connection to Google Calendar!")
        items = events.get('items', [])
        print(f"[*] Total upcoming items found: {len(items)}")
        for idx, item in enumerate(items, 1):
            print(f"    {idx}. {item.get('summary', 'Untitled')}")
    except Exception as e:
        print(f"[!] Warning: Could not run test query: {e}")


def _verify_pure_requests(token_payload):
    """Verifies connection using requests."""
    try:
        headers = {"Authorization": f"Bearer {token_payload['token']}"}
        resp = requests.get("https://www.googleapis.com/calendar/v3/calendars/primary/events?maxResults=3", headers=headers, timeout=10)
        if resp.status_code == 200:
            print("[✓] Successfully verified connection to Google Calendar!")
            data = resp.json()
            items = data.get('items', [])
            print(f"[*] Total upcoming items found: {len(items)}")
            for idx, item in enumerate(items, 1):
                print(f"    {idx}. {item.get('summary', 'Untitled')}")
        else:
            print(f"[!] Test fetch returned {resp.status_code}: {resp.text}")
    except Exception as e:
        print(f"[!] Warning: Could not run test query: {e}")


if __name__ == "__main__":
    main()
