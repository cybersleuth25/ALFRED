"""
Spotify OAuth Setup for Alfred.
================================
One-time script to authorize Alfred to access your Spotify playback.

Usage:
    python spotify_auth.py

This will:
1. Open your browser to log in to Spotify
2. Ask you to authorize Alfred
3. Save the refresh token to .env for permanent access

BEFORE RUNNING:
- Go to https://developer.spotify.com/dashboard
- Select your app (or create one)
- Add http://localhost:8888/callback as a Redirect URI in your app settings
"""

import os
import sys
import webbrowser
import urllib.parse
import base64
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from dotenv import load_dotenv, set_key

load_dotenv()

CLIENT_ID = "20caa4dbf24e4c288bbaad1e2c0d576d"
CLIENT_SECRET = "6bf42c1ee9c647d3be1978467910576c"
REDIRECT_URI = "http://127.0.0.1:8888/callback"
SCOPES = "user-read-currently-playing user-read-playback-state user-modify-playback-state user-read-recently-played"

ENV_PATH = os.path.join(os.path.dirname(__file__), ".env")

# Will be set by the callback handler
_auth_code = None


class CallbackHandler(BaseHTTPRequestHandler):
    """Handles the OAuth callback from Spotify."""

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
                <html><body style="background:#0a0a0a;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0">
                <div style="text-align:center">
                    <h1 style="color:#1DB954;font-weight:300">&#10003; Authorization Successful</h1>
                    <p style="color:#888">Alfred now has access to your Spotify playback. You may close this tab.</p>
                </div>
                </body></html>
            """)
        else:
            error = params.get("error", ["Unknown error"])[0]
            _auth_code = None
            self.send_response(400)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(f"<html><body><h1>Error: {error}</h1></body></html>".encode())

    def log_message(self, format, *args):
        pass  # Suppress console output


def main():
    print("=" * 50)
    print("  ALFRED — Spotify Authorization Setup")
    print("=" * 50)
    print()
    print("IMPORTANT: Before continuing, make sure you have added")
    print(f"  {REDIRECT_URI}")
    print("as a Redirect URI in your Spotify Developer Dashboard.")
    print()
    input("Press Enter to open Spotify login in your browser...")

    # Step 1: Open browser for user authorization
    auth_url = (
        "https://accounts.spotify.com/authorize?"
        + urllib.parse.urlencode({
            "client_id": CLIENT_ID,
            "response_type": "code",
            "redirect_uri": REDIRECT_URI,
            "scope": SCOPES,
            "show_dialog": "true",
        })
    )

    webbrowser.open(auth_url)
    print("\n[Waiting for Spotify login...]")

    # Step 2: Start local server to catch the callback
    server = HTTPServer(("127.0.0.1", 8888), CallbackHandler)
    
    while not _auth_code:
        server.handle_request()

    print("[OK] Authorization code received. Exchanging for tokens...")

    # Step 3: Exchange auth code for access + refresh tokens
    auth_string = f"{CLIENT_ID}:{CLIENT_SECRET}"
    auth_b64 = base64.b64encode(auth_string.encode()).decode()

    token_resp = requests.post(
        "https://accounts.spotify.com/api/token",
        headers={
            "Authorization": f"Basic {auth_b64}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={
            "grant_type": "authorization_code",
            "code": _auth_code,
            "redirect_uri": REDIRECT_URI,
        },
    )

    if token_resp.status_code != 200:
        print(f"\n[ERROR] Token exchange failed: {token_resp.text}")
        sys.exit(1)

    tokens = token_resp.json()
    refresh_token = tokens.get("refresh_token", "")
    access_token = tokens.get("access_token", "")

    if not refresh_token:
        print("\n[ERROR] No refresh token received.")
        sys.exit(1)

    # Step 4: Save refresh token to .env
    set_key(ENV_PATH, "SPOTIFY_REFRESH_TOKEN", refresh_token)
    print(f"\n[OK] Refresh token saved to .env")

    # Step 5: Quick test — get current user profile
    try:
        me = requests.get(
            "https://api.spotify.com/v1/me",
            headers={"Authorization": f"Bearer {access_token}"},
        ).json()
        display_name = me.get("display_name", "Unknown")
        print(f"[OK] Connected as: {display_name}")
    except Exception:
        pass

    print()
    print("=" * 50)
    print("  Setup complete! Alfred can now control Spotify.")
    print("=" * 50)
    print()
    print("Alfred can now:")
    print("  - Tell you what song is playing")
    print("  - Pause, resume, skip, and go back")
    print("  - See your recently played tracks")


if __name__ == "__main__":
    main()
