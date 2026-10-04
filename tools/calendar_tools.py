"""
Google Calendar Tool for JARVIS / Alfred.
=========================================
Provides bidirectional synchronization with Google Calendar and Samsung Calendar.
Supports:
- Querying events for today, tomorrow, specific dates (e.g. 'Oct 15', 'Monday'), or ranges.
- Creating events with flexible natural time parsing ('tomorrow at 4pm', 'in 2 hours', 'Monday at 10am').
- Deleting/cancelling events by name or ID.
- Multi-calendar support (reads primary + shared calendars from other Gmail accounts).

Requires OAuth 2.0 authorization.
Run `python google_calendar_auth.py` once to authorize.
"""

import os
import json
import re
from datetime import datetime, timedelta, timezone, time as dt_time
from typing import Optional, List, Dict, Any

# Scopes required for read and write calendar access
SCOPES = ['https://www.googleapis.com/auth/calendar']

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKEN_PATH = os.path.join(BASE_DIR, "token.json")
CREDENTIALS_PATH = os.path.join(BASE_DIR, "credentials.json")


def is_calendar_authenticated() -> bool:
    """Returns True if a valid or refreshable token is present."""
    if not os.path.exists(TOKEN_PATH):
        return False
    try:
        from google.oauth2.credentials import Credentials
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
        return creds is not None and (creds.valid or bool(creds.refresh_token))
    except Exception:
        return False


def _get_service():
    """Builds and returns the Google Calendar API service with automatic token refresh."""
    if not os.path.exists(TOKEN_PATH):
        return None

    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build

        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                with open(TOKEN_PATH, 'w', encoding='utf-8') as token_file:
                    token_file.write(creds.to_json())
            except Exception as e:
                print(f"[Calendar] Failed to refresh token: {e}")
                return None

        if creds and creds.valid:
            return build('calendar', 'v3', credentials=creds, cache_discovery=False)
        return None
    except Exception as e:
        print(f"[Calendar] Error initializing Google Calendar service: {e}")
        return None


def _format_event_time(dt_iso: str) -> str:
    """Formats an ISO datetime or date string into a user-friendly string."""
    try:
        # Check if full date string (all-day event)
        if len(dt_iso) == 10 and dt_iso.count('-') == 2:
            event_date = datetime.strptime(dt_iso, "%Y-%m-%d").date()
            today = datetime.now().date()
            if event_date == today:
                return "All day today"
            elif event_date == today + timedelta(days=1):
                return "All day tomorrow"
            return event_date.strftime("%a, %b %d (All day)")

        clean_iso = dt_iso.replace('Z', '+00:00')
        dt = datetime.fromisoformat(clean_iso)
        if dt.tzinfo:
            dt = dt.astimezone()

        today = datetime.now().date()
        if dt.date() == today:
            return f"Today at {dt.strftime('%I:%M %p').lstrip('0')}"
        elif dt.date() == today + timedelta(days=1):
            return f"Tomorrow at {dt.strftime('%I:%M %p').lstrip('0')}"
        else:
            return dt.strftime("%a, %b %d at %I:%M %p").replace(" 0", " ")
    except Exception:
        return dt_iso


def _parse_time_input(time_str: str) -> datetime:
    """
    Parses flexible human datetime formats into a datetime object.
    Supports:
    - 'tomorrow at 4pm', 'tomorrow 16:00', 'tomorrow at 10:30 am'
    - 'today at 5pm', 'today 5:30pm'
    - 'Monday at 10am', 'Friday at 3pm'
    - 'in 2 hours', 'in 45 minutes', 'in 3 days'
    - 'Oct 15 at 3pm', '2026-10-15 14:00'
    - '4pm', '14:30' (assumes today, or tomorrow if time has passed)
    """
    now = datetime.now()
    raw = time_str.strip()
    clean = raw.lower().replace("p.m.", "pm").replace("a.m.", "am").replace("p.m", "pm").replace("a.m", "am")

    # 1. Relative offset expressions: "in 2 hours", "in 30 mins", "in 1 day"
    m_rel = re.search(r'\bin\s+(\d+)\s*(mins?|minutes?|hours?|hrs?|h\b|days?|d\b)', clean)
    if m_rel:
        val = int(m_rel.group(1))
        unit = m_rel.group(2)
        if 'min' in unit:
            return now + timedelta(minutes=val)
        elif 'hour' in unit or 'hr' in unit or unit == 'h':
            return now + timedelta(hours=val)
        elif 'day' in unit or unit == 'd':
            return now + timedelta(days=val)

    # 2. Weekday matching (e.g., "Monday at 3pm", "this Friday at 10am")
    weekdays = {
        'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
        'friday': 4, 'saturday': 5, 'sunday': 6
    }
    for day_name, day_idx in weekdays.items():
        if day_name in clean:
            days_ahead = (day_idx - now.weekday()) % 7
            if days_ahead == 0 and "next" in clean:
                days_ahead = 7
            elif days_ahead == 0:
                # If today is Monday and time passed, next week
                pass
            target_date = (now + timedelta(days=days_ahead if days_ahead > 0 else 7)).date()
            # Strip weekday word and "next", "this", "on", "at"
            rem = re.sub(rf'\b(next|this|on|at|{day_name})\b', ' ', clean).strip()
            time_part = _parse_clock_time(rem) or dt_time(hour=9, minute=0)
            return datetime.combine(target_date, time_part)

    # 3. "tomorrow" handling (e.g. "tomorrow at 4pm", "tomorrow 16:00", "tomorrow")
    if "tomorrow" in clean:
        target_date = (now + timedelta(days=1)).date()
        rem = clean.replace("tomorrow", " ").replace("at", " ").replace("for", " ").strip()
        time_part = _parse_clock_time(rem) or dt_time(hour=9, minute=0)
        return datetime.combine(target_date, time_part)

    # 4. "today" handling (e.g. "today at 5pm", "today 17:00")
    if "today" in clean:
        target_date = now.date()
        rem = clean.replace("today", " ").replace("at", " ").replace("for", " ").strip()
        time_part = _parse_clock_time(rem) or dt_time(hour=(now.hour + 1) % 24, minute=0)
        return datetime.combine(target_date, time_part)

    # 5. Dateutil parser with fuzzy matching
    try:
        from dateutil import parser
        cleaned_str = re.sub(r'\b(at|on|for)\b', ' ', raw, flags=re.IGNORECASE).strip()
        parsed = parser.parse(cleaned_str, default=now, fuzzy=True)
        # If user only specified a time that has already passed today, push to tomorrow
        has_date_spec = any(w in clean for w in [
            'jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec',
            '202', 'tomorrow', 'today', 'yesterday'
        ]) or re.search(r'\d{1,2}[/-]\d{1,2}', clean)
        if not has_date_spec and parsed < now:
            parsed = parsed + timedelta(days=1)
        return parsed
    except Exception:
        pass

    # 6. Time-only fallback ("4pm", "16:00", "4:30 pm")
    t = _parse_clock_time(clean)
    if t:
        parsed = datetime.combine(now.date(), t)
        if parsed < now:
            parsed = parsed + timedelta(days=1)
        return parsed

    raise ValueError(f"Could not understand date/time: '{time_str}'. Try e.g. 'tomorrow at 4pm' or 'Monday at 10am'.")


def _parse_clock_time(text: str) -> Optional[dt_time]:
    """Helper to extract clock time like 4pm, 4:30pm, 16:00, 10 am from string."""
    clean = text.strip().lower().replace("p.m.", "pm").replace("a.m.", "am").replace("p.m", "pm").replace("a.m", "am")
    
    # Check 12-hour with am/pm (e.g., 4:30 pm, 4pm, 11:15am)
    m12 = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)', clean)
    if m12:
        hour = int(m12.group(1))
        minute = int(m12.group(2)) if m12.group(2) else 0
        ampm = m12.group(3)
        if ampm == 'pm' and hour < 12:
            hour += 12
        elif ampm == 'am' and hour == 12:
            hour = 0
        return dt_time(hour=hour, minute=minute)

    # Check 24-hour time (e.g., 14:00, 09:30)
    m24 = re.search(r'\b([01]?\d|2[0-3]):([0-5]\d)\b', clean)
    if m24:
        return dt_time(hour=int(m24.group(1)), minute=int(m24.group(2)))

    # Check single number if context implies hour: e.g. "at 4"
    m_hour = re.search(r'\b(\d{1,2})\b', clean)
    if m_hour:
        h = int(m_hour.group(1))
        if 1 <= h <= 24:
            # Default to daytime/afternoon for small numbers
            if 1 <= h <= 6:
                h += 12
            return dt_time(hour=h % 24, minute=0)

    return None


def _resolve_query_time_range(query_date: str = "", days: int = 1):
    """
    Resolves start and end ISO timestamps for calendar queries.
    Handles 'today', 'tomorrow', 'yesterday', weekday names ('Monday'),
    specific dates ('Oct 15', '2026-10-15'), or relative days.
    """
    now = datetime.now()
    clean = query_date.strip().lower()

    if not clean or clean == "today":
        start_dt = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_dt = (start_dt + timedelta(days=max(1, days) - 1)).replace(hour=23, minute=59, second=59)
        date_label = "today" if days == 1 else f"the next {days} days"
        return start_dt, end_dt, date_label

    if clean == "tomorrow":
        start_dt = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        end_dt = (start_dt + timedelta(days=max(1, days) - 1)).replace(hour=23, minute=59, second=59)
        date_label = "tomorrow"
        return start_dt, end_dt, date_label

    if clean == "yesterday":
        start_dt = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        end_dt = start_dt.replace(hour=23, minute=59, second=59)
        date_label = "yesterday"
        return start_dt, end_dt, date_label

    # Check weekday name (e.g. "Monday", "this Friday")
    weekdays = {'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3, 'friday': 4, 'saturday': 5, 'sunday': 6}
    for wname, wday in weekdays.items():
        if wname in clean:
            offset = (wday - now.weekday()) % 7
            if offset == 0 and "next" in clean:
                offset = 7
            target = (now + timedelta(days=offset)).replace(hour=0, minute=0, second=0, microsecond=0)
            end_dt = target.replace(hour=23, minute=59, second=59)
            date_label = target.strftime("%A, %b %d")
            return target, end_dt, date_label

    # Specific date parsing via dateutil
    try:
        from dateutil import parser
        parsed = parser.parse(query_date, default=now, fuzzy=True)
        start_dt = parsed.replace(hour=0, minute=0, second=0, microsecond=0)
        end_dt = (start_dt + timedelta(days=max(1, days) - 1)).replace(hour=23, minute=59, second=59)
        date_label = start_dt.strftime("%A, %b %d")
        return start_dt, end_dt, date_label
    except Exception:
        pass

    # Fallback to next N days
    start_dt = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_dt = (start_dt + timedelta(days=max(1, days))).replace(hour=23, minute=59, second=59)
    return start_dt, end_dt, f"the next {days} days"


def get_calendar_events(query_date: str = "", days: int = 1, max_results: int = 20) -> str:
    """
    Fetches upcoming calendar events for a specific date, date description, or day count.
    Supports queries across primary and secondary/shared Gmail accounts!

    Parameters:
    - query_date: Date to inspect (e.g. 'today', 'tomorrow', 'Monday', 'Oct 15', '2026-10-15'). Leave empty for today.
    - days: Number of days to include starting from the query_date (default 1).
    - max_results: Maximum events to return (default 20).
    """
    service = _get_service()
    if not service:
        if not os.path.exists(TOKEN_PATH):
            return "Google Calendar is not linked yet. Please run 'python google_calendar_auth.py' to connect your Google & Samsung Calendar."
        return "Could not connect to Google Calendar. Your session may have expired; please re-run 'python google_calendar_auth.py'."

    try:
        days = int(days)
        max_results = int(max_results)
    except Exception:
        days = 1
        max_results = 20

    start_dt, end_dt, date_label = _resolve_query_time_range(query_date, days)

    # Convert to UTC ISO format for API
    local_tz = datetime.now().astimezone().tzinfo
    time_min = start_dt.astimezone(timezone.utc).isoformat()
    time_max = end_dt.astimezone(timezone.utc).isoformat()

    try:
        # Retrieve all accessible calendars (Primary + shared calendars from other Gmail accounts)
        calendar_ids = ['primary']
        try:
            cal_list_resp = service.calendarList().list().execute()
            for cal in cal_list_resp.get('items', []):
                cal_id = cal.get('id')
                if cal_id and cal_id != 'primary' and cal.get('selected', True):
                    # Skip holiday spam if desired, or include all
                    calendar_ids.append(cal_id)
        except Exception:
            pass

        all_items = []
        seen_ids = set()

        for cal_id in calendar_ids:
            try:
                events_result = service.events().list(
                    calendarId=cal_id,
                    timeMin=time_min,
                    timeMax=time_max,
                    maxResults=max_results,
                    singleEvents=True,
                    orderBy='startTime'
                ).execute()
                for item in events_result.get('items', []):
                    item_id = item.get('id')
                    if item_id and item_id not in seen_ids:
                        seen_ids.add(item_id)
                        all_items.append(item)
            except Exception:
                continue

        if not all_items:
            return f"You have no events scheduled for {date_label}."

        # Sort all items by start time
        def _get_sort_key(item):
            st = item.get('start', {})
            return st.get('dateTime') or st.get('date') or ''

        all_items.sort(key=_get_sort_key)
        all_items = all_items[:max_results]

        lines = [f"Here is your schedule for {date_label}:"]
        for idx, event in enumerate(all_items, 1):
            summary = event.get('summary', 'Untitled Event')
            start = event.get('start', {}).get('dateTime', event.get('start', {}).get('date', ''))
            time_formatted = _format_event_time(start)
            location = event.get('location')
            meet_link = event.get('hangoutLink')

            line = f"{idx}. {summary} — {time_formatted}"
            if location:
                line += f" ({location})"
            elif meet_link:
                line += f" [Google Meet]"
            lines.append(line)

        return "\n".join(lines)
    except Exception as e:
        return f"Error retrieving calendar events for {date_label}: {e}"


_cached_user_timezone = None


def _get_primary_timezone(service) -> str:
    """Retrieves and caches the user's primary calendar IANA timezone (e.g. 'Asia/Kolkata')."""
    global _cached_user_timezone
    if _cached_user_timezone:
        return _cached_user_timezone
    try:
        cal_meta = service.calendars().get(calendarId='primary').execute()
        tz = cal_meta.get('timeZone')
        if tz and "/" in tz:
            _cached_user_timezone = tz
            return _cached_user_timezone
    except Exception:
        pass
    return "Asia/Kolkata"


def create_calendar_event(
    title: str,
    start_time: str,
    duration_minutes: int = 60,
    description: str = "",
    location: str = ""
) -> str:
    """
    Creates a new event on your Google Calendar (syncs with Samsung Calendar).
    
    Parameters:
    - title: Event title/summary (e.g. 'Meeting with Alex')
    - start_time: Start date/time (e.g. 'tomorrow at 4pm', 'Monday at 10am', '2026-10-05 14:00')
    - duration_minutes: Duration in minutes (default 60)
    - description: Optional event notes
    - location: Optional location or meeting link
    """
    service = _get_service()
    if not service:
        return "Google Calendar is not linked yet. Please run 'python google_calendar_auth.py' first."

    try:
        duration_minutes = int(duration_minutes)
    except Exception:
        duration_minutes = 60

    try:
        start_dt = _parse_time_input(start_time)
        end_dt = start_dt + timedelta(minutes=duration_minutes)
    except Exception as e:
        return f"Failed to parse event time: {e}"

    # Get valid IANA timezone (e.g. Asia/Kolkata)
    user_tz = _get_primary_timezone(service)

    # Attach local system timezone offset
    if start_dt.tzinfo is None:
        local_tz = datetime.now().astimezone().tzinfo
        start_dt = start_dt.replace(tzinfo=local_tz)
        end_dt = end_dt.replace(tzinfo=local_tz)

    event_body: Dict[str, Any] = {
        'summary': title,
        'description': description,
        'start': {
            'dateTime': start_dt.isoformat(),
            'timeZone': user_tz,
        },
        'end': {
            'dateTime': end_dt.isoformat(),
            'timeZone': user_tz,
        },
    }

    if location:
        event_body['location'] = location

    try:
        created_event = service.events().insert(calendarId='primary', body=event_body).execute()
        time_str = start_dt.strftime("%A, %b %d at %I:%M %p").replace(" 0", " ")
        return f"Event '{title}' has been successfully scheduled for {time_str} ({duration_minutes} minutes) on your Google & Samsung Calendar."
    except Exception as e:
        return f"Error creating calendar event: {e}"


def delete_calendar_event(query: str) -> str:
    """
    Deletes an event from Google Calendar matching a title or event ID.
    Searches upcoming events for matching title.
    """
    service = _get_service()
    if not service:
        return "Google Calendar is not linked yet. Please run 'python google_calendar_auth.py'."

    query_clean = query.strip().lower()

    now = datetime.now(timezone.utc).isoformat()
    future = (datetime.now(timezone.utc) + timedelta(days=60)).isoformat()

    try:
        events_result = service.events().list(
            calendarId='primary',
            timeMin=now,
            timeMax=future,
            maxResults=50,
            singleEvents=True
        ).execute()

        items = events_result.get('items', [])
        match = None
        for item in items:
            summary = item.get('summary', '').lower()
            event_id = item.get('id', '')
            if query_clean == event_id.lower() or query_clean in summary:
                match = item
                break

        if not match:
            try:
                service.events().delete(calendarId='primary', eventId=query.strip()).execute()
                return f"Event with ID '{query}' deleted successfully."
            except Exception:
                return f"Could not find an upcoming event matching '{query}' to delete."

        target_id = match['id']
        target_summary = match.get('summary', 'Untitled')
        target_start = _format_event_time(match.get('start', {}).get('dateTime', match.get('start', {}).get('date', '')))

        service.events().delete(calendarId='primary', eventId=target_id).execute()
        return f"Event '{target_summary}' ({target_start}) has been removed from your calendar."
    except Exception as e:
        return f"Error deleting calendar event: {e}"


def get_today_events_summary() -> str:
    """
    Generates a concise 1-sentence schedule summary for the morning briefing or status checks.
    Returns empty string if no events or unlinked.
    """
    service = _get_service()
    if not service:
        return ""

    try:
        local_now = datetime.now()
        start_of_day = local_now.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc).isoformat()
        end_of_day = local_now.replace(hour=23, minute=59, second=59, microsecond=999999).astimezone(timezone.utc).isoformat()

        events_result = service.events().list(
            calendarId='primary',
            timeMin=start_of_day,
            timeMax=end_of_day,
            maxResults=10,
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        items = events_result.get('items', [])
        if not items:
            return "No scheduled calendar events for today."

        count = len(items)
        first_event = items[0]
        first_title = first_event.get('summary', 'an event')
        first_start = first_event.get('start', {}).get('dateTime', '')
        time_part = ""
        if first_start:
            dt = datetime.fromisoformat(first_start.replace('Z', '+00:00')).astimezone()
            time_part = f" at {dt.strftime('%I:%M %p').lstrip('0')}"

        if count == 1:
            return f"You have 1 calendar event today: '{first_title}'{time_part}."
        elif count == 2:
            second_title = items[1].get('summary', 'an event')
            return f"You have 2 events today: '{first_title}'{time_part} and '{second_title}'."
        else:
            return f"You have {count} events on your schedule today, beginning with '{first_title}'{time_part}."
    except Exception as e:
        print(f"[Calendar] Briefing summary error: {e}")
        return ""


def detect_schedule_conflicts(date_str: str = "today") -> str:
    """
    Analyzes events for a given day and detects any double-bookings or overlapping events.
    """
    service = _get_service()
    if not service:
        return "Google Calendar is not linked. Please run 'python google_calendar_auth.py'."

    try:
        start_dt, end_dt, date_label = _resolve_query_time_range(date_str, 1)
        time_min = start_dt.astimezone(timezone.utc).isoformat()
        time_max = end_dt.astimezone(timezone.utc).isoformat()

        events_result = service.events().list(
            calendarId='primary',
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        items = events_result.get('items', [])
        timed_events = []
        for it in items:
            start_dt_str = it.get('start', {}).get('dateTime')
            end_dt_str = it.get('end', {}).get('dateTime')
            if start_dt_str and end_dt_str:
                s = datetime.fromisoformat(start_dt_str.replace('Z', '+00:00')).astimezone()
                e = datetime.fromisoformat(end_dt_str.replace('Z', '+00:00')).astimezone()
                timed_events.append((it.get('summary', 'Untitled Event'), s, e))

        if len(timed_events) < 2:
            return f"✅ No schedule conflicts detected for {date_label}."

        conflicts = []
        for i in range(len(timed_events) - 1):
            title1, s1, e1 = timed_events[i]
            title2, s2, e2 = timed_events[i + 1]
            if s2 < e1:
                # Overlap!
                conflicts.append(
                    f"⚠️ **Conflict Alert:**\n"
                    f"  • '{title1}' ({s1.strftime('%I:%M %p')} - {e1.strftime('%I:%M %p')})\n"
                    f"  • Overlaps with '{title2}' ({s2.strftime('%I:%M %p')} - {e2.strftime('%I:%M %p')})"
                )

        if not conflicts:
            return f"✅ Clean schedule! No overlapping meetings or conflicts for {date_label}."

        return f"🚨 **{len(conflicts)} Schedule Conflict(s) Detected for {date_label}:**\n\n" + "\n\n".join(conflicts)

    except Exception as e:
        return f"Error checking schedule conflicts: {e}"


def find_focus_slots(date_str: str = "today", min_minutes: int = 60) -> str:
    """
    Finds open blocks of uninterrupted time for deep work/study between 9:00 AM and 8:00 PM.
    """
    service = _get_service()
    if not service:
        return "Google Calendar is not linked."

    try:
        start_dt, end_dt, date_label = _resolve_query_time_range(date_str, 1)
        time_min = start_dt.astimezone(timezone.utc).isoformat()
        time_max = end_dt.astimezone(timezone.utc).isoformat()

        events_result = service.events().list(
            calendarId='primary',
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        items = events_result.get('items', [])
        day_start = start_dt.replace(hour=9, minute=0, second=0, microsecond=0).astimezone()
        day_end = start_dt.replace(hour=20, minute=0, second=0, microsecond=0).astimezone()


        busy_blocks = []
        for it in items:
            s_str = it.get('start', {}).get('dateTime')
            e_str = it.get('end', {}).get('dateTime')
            if s_str and e_str:
                s = datetime.fromisoformat(s_str.replace('Z', '+00:00')).astimezone()
                e = datetime.fromisoformat(e_str.replace('Z', '+00:00')).astimezone()
                busy_blocks.append((max(s, day_start), min(e, day_end)))

        busy_blocks.sort(key=lambda x: x[0])

        # Merge overlapping busy blocks
        merged_busy = []
        for b_start, b_end in busy_blocks:
            if not merged_busy:
                merged_busy.append([b_start, b_end])
            else:
                last_end = merged_busy[-1][1]
                if b_start <= last_end:
                    merged_busy[-1][1] = max(last_end, b_end)
                else:
                    merged_busy.append([b_start, b_end])

        # Find gaps between merged busy blocks
        free_slots = []
        current_pointer = day_start
        for b_start, b_end in merged_busy:
            if b_start > current_pointer:
                duration_m = int((b_start - current_pointer).total_seconds() // 60)
                if duration_m >= min_minutes:
                    free_slots.append((current_pointer, b_start, duration_m))
            current_pointer = max(current_pointer, b_end)

        if current_pointer < day_end:
            duration_m = int((day_end - current_pointer).total_seconds() // 60)
            if duration_m >= min_minutes:
                free_slots.append((current_pointer, day_end, duration_m))

        if not free_slots:
            return f"📅 Schedule for {date_label} is tightly packed with no uninterrupted {min_minutes}m focus blocks."

        lines = [f"🎯 **Recommended Deep Work & Focus Slots for {date_label}**:\n"]
        for s, e, dur in free_slots:
            hours = dur // 60
            mins = dur % 60
            dur_str = f"{hours}h {mins}m" if hours else f"{mins}m"
            lines.append(f"• **{s.strftime('%I:%M %p')} – {e.strftime('%I:%M %p')}** ({dur_str} uninterrupted block)")

        return "\n".join(lines)

    except Exception as e:
        return f"Error finding focus slots: {e}"

