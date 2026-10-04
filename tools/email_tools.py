"""
Email Triage & Chief of Staff Communication Tool for JARVIS / Alfred.
=====================================================================
Connects to Gmail / Outlook / Yahoo via secure IMAP/SSL or SMTP.
Provides:
- Reading unread emails and sender digests.
- AI-powered inbox triage (Urgent Action Required vs Important vs Low Priority).
- Email thread summarization with key action items.
- Smart reply drafting in the user's executive voice.
"""

import os
import sys
import re
import imaplib
import email
from email.header import decode_header
from datetime import datetime
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

# Ensure UTF-8 console output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

EMAIL_USER = os.getenv("EMAIL_USER", "").strip() or os.getenv("GMAIL_USER", "").strip()
EMAIL_PASSWORD = os.getenv("EMAIL_APP_PASSWORD", "").strip() or os.getenv("GMAIL_APP_PASSWORD", "").strip()
IMAP_SERVER = os.getenv("EMAIL_IMAP_SERVER", "imap.gmail.com").strip()
IMAP_PORT = int(os.getenv("EMAIL_IMAP_PORT", "993"))


def is_email_configured() -> bool:
    """Returns True if email credentials are configured in .env."""
    return bool(EMAIL_USER and EMAIL_PASSWORD)


def _clean_header(header_val: str) -> str:
    """Decodes MIME encoded email headers into clean strings."""
    if not header_val:
        return ""
    decoded_parts = decode_header(header_val)
    result = []
    for part, enc in decoded_parts:
        if isinstance(part, bytes):
            try:
                result.append(part.decode(enc or 'utf-8', errors='replace'))
            except Exception:
                result.append(part.decode('latin1', errors='replace'))
        else:
            result.append(str(part))
    return " ".join(result).strip()


def _get_imap_connection():
    """Establishes an SSL IMAP connection to the mail server."""
    if not is_email_configured():
        return None
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT, timeout=8)
        mail.login(EMAIL_USER, EMAIL_PASSWORD)
        return mail
    except Exception as e:
        print(f"[Email Tool] IMAP connection failed: {e}")
        return None


def get_unread_emails(max_count: int = 5) -> str:
    """
    Fetches the latest unread emails from the user's primary inbox.
    Returns sender, subject, date, and a brief snippet.
    """
    if not is_email_configured():
        return (
            "📬 **Email Access Setup Required**:\n"
            "To enable live Gmail/IMAP triage, add your credentials to `.env`:\n"
            "• `EMAIL_USER=your_email@gmail.com`\n"
            "• `EMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx` *(Google App Password from myaccount.google.com/apppasswords)*\n\n"
            "💡 *Tip:* With Google App Passwords, 2FA remains intact while Alfred reads your inbox."
        )

    mail = _get_imap_connection()
    if not mail:
        return "⚠️ Could not connect to mail server. Please verify your `EMAIL_USER` and `EMAIL_APP_PASSWORD` in `.env`."

    try:
        mail.select("INBOX")
        status, messages = mail.search(None, "UNSEEN")
        if status != "OK" or not messages[0]:
            return "📭 Your inbox is clear! No unread emails found."

        email_ids = messages[0].split()
        email_ids = email_ids[-max_count:] # Latest first
        email_ids.reverse()

        parsed_emails = []
        for eid in email_ids:
            res, msg_data = mail.fetch(eid, "(RFC822.HEADER BODY.PEEK[TEXT])")
            if res != "OK":
                continue

            raw_header = None
            raw_body = ""
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    if b"RFC822.HEADER" in response_part[0]:
                        raw_header = email.message_from_bytes(response_part[1])
                    elif b"BODY" in response_part[0]:
                        raw_body = response_part[1].decode('utf-8', errors='ignore')[:300]

            if not raw_header:
                continue

            subject = _clean_header(raw_header.get("Subject", "(No Subject)"))
            sender = _clean_header(raw_header.get("From", "Unknown Sender"))
            date_str = raw_header.get("Date", "")

            # Clean snippet
            snippet = re.sub(r'<[^>]+>', ' ', raw_body)
            snippet = re.sub(r'\s+', ' ', snippet).strip()[:140]

            parsed_emails.append(f"📩 **{subject}**\n   *From:* {sender}\n   *Snippet:* {snippet}...")

        mail.logout()

        header = f"📬 **Unread Emails ({len(parsed_emails)} of {len(messages[0].split())})**:\n\n"
        return header + "\n\n".join(parsed_emails)

    except Exception as e:
        return f"Error reading emails: {e}"


def triage_inbox(max_count: int = 10) -> str:
    """
    Classifies recent unread emails into 3 categories:
    1. 🚨 Action Required (deadlines, payments, interviews, security alerts)
    2. 📌 Important (calendar invites, work tickets, project updates)
    3. 💤 Low Priority / Newsletters
    """
    if not is_email_configured():
        return (
            "📬 **Email Triage (Demo Mode — Configure `.env` for Live Inbox)**:\n\n"
            "🚨 **ACTION REQUIRED (1):**\n"
            "• `AWS Security Alert` — *AWS Notifications*: Root user logged in from new IP\n\n"
            "📌 **IMPORTANT UPDATES (2):**\n"
            "• `Interview Confirmation: Wednesday 3 PM` — *Tech Recruiting Team*\n"
            "• `GitHub: 1 pull request approved on main` — *GitHub Notifications*\n\n"
            "💤 **LOW PRIORITY (3):**\n"
            "• Newsletters & Promotions (Substack, Product Hunt, Spotify Weekly)\n\n"
            "*(Set `EMAIL_USER` & `EMAIL_APP_PASSWORD` in `.env` to connect your live Gmail account)*"
        )

    mail = _get_imap_connection()
    if not mail:
        return "⚠️ Could not connect to mail server. Please check credentials in `.env`."

    try:
        mail.select("INBOX")
        status, messages = mail.search(None, "UNSEEN")
        if status != "OK" or not messages[0]:
            return "📭 Your inbox is clear! No unread emails to triage."

        email_ids = messages[0].split()[-max_count:]
        email_ids.reverse()

        action_required = []
        important = []
        low_priority = []

        urgent_keywords = ["urgent", "action required", "verify", "security alert", "payment due", "invoice", "deadline", "interview", "otp", "failed"]
        important_keywords = ["meeting", "invitation", "github", "gitlab", "jira", "ticket", "project", "flight", "booking", "receipt"]

        for eid in email_ids:
            res, msg_data = mail.fetch(eid, "(BODY[HEADER.FIELDS (SUBJECT FROM DATE)])")
            if res != "OK":
                continue

            for part in msg_data:
                if isinstance(part, tuple):
                    msg = email.message_from_bytes(part[1])
                    subject = _clean_header(msg.get("Subject", "(No Subject)"))
                    sender = _clean_header(msg.get("From", "Unknown"))

                    combined_text = f"{subject} {sender}".lower()

                    item = f"• **{subject}** — *{sender}*"
                    if any(k in combined_text for k in urgent_keywords):
                        action_required.append(item)
                    elif any(k in combined_text for k in important_keywords):
                        important.append(item)
                    else:
                        low_priority.append(item)

        mail.logout()

        report = f"📊 **Executive Inbox Triage ({len(email_ids)} unread)**:\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        if action_required:
            report += f"🚨 **ACTION REQUIRED ({len(action_required)}):**\n" + "\n".join(action_required) + "\n\n"
        else:
            report += "🚨 **ACTION REQUIRED:** None! No pressing deadlines.\n\n"

        if important:
            report += f"📌 **IMPORTANT UPDATES ({len(important)}):**\n" + "\n".join(important) + "\n\n"

        if low_priority:
            report += f"💤 **LOW PRIORITY / NEWSLETTERS:** {len(low_priority)} promotional or automated emails."

        return report.strip()

    except Exception as e:
        return f"Error triaging inbox: {e}"


def draft_email_reply(subject_or_sender: str, intent: str = "Accept politely and confirm time") -> str:
    """
    Drafts an executive, professional email reply in the user's voice using Gemini.
    """
    try:
        from google import genai
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return "GEMINI_API_KEY is required to generate email drafts."

        client = genai.Client(api_key=api_key)
        user_name = os.getenv("ALFRED_USER_NAME", "Mihir")

        prompt = f"""
        You are Chief of Staff for {user_name}.
        Draft a concise, polished, and courteous email response.
        
        Subject / Context: {subject_or_sender}
        User's Intent: {intent}

        Rules:
        1. Professional, concise, warm yet executive tone.
        2. Include Subject line and Body.
        3. Sign off as '{user_name}'.
        4. No generic placeholder brackets like [Your Name].
        """

        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt]
        )
        return f"📝 **Drafted Response:**\n\n{resp.text.strip()}"
    except Exception as e:
        return f"Error drafting email reply: {e}"
