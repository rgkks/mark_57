import json
import os
import uuid
import threading
import time
from datetime import datetime, timedelta

REMINDERS_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Data", "Reminders.json")

def _load():
    try:
        if os.path.exists(REMINDERS_PATH):
            with open(REMINDERS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return []

def _save(reminders):
    os.makedirs(os.path.dirname(REMINDERS_PATH), exist_ok=True)
    with open(REMINDERS_PATH, "w", encoding="utf-8") as f:
        json.dump(reminders, f, indent=4, ensure_ascii=False)

def _parse_time(time_str):
    time_str = time_str.strip().lower()
    now = datetime.now()

    if "tomorrow" in time_str:
        base = now + timedelta(days=1)
        time_str = time_str.replace("tomorrow", "").strip()
    elif "today" in time_str:
        base = now
        time_str = time_str.replace("today", "").strip()
    elif "next week" in time_str:
        base = now + timedelta(weeks=1)
        time_str = time_str.replace("next week", "").strip()
    else:
        base = now

    time_str = time_str.replace("at ", "").replace("by ", "").strip()

    import re
    time_match = re.search(r'(\d{1,2}(?::\d{2})?\s*(?:am|pm|a\.m\.|p\.m\.))', time_str)
    if time_match:
        time_part = time_match.group(1).replace(" ", "")
        for fmt in ("%I:%M%p", "%I%p"):
            try:
                t = datetime.strptime(time_part, fmt)
                return base.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)
            except ValueError:
                continue

    time_match = re.search(r'(\d{1,2}:\d{2})', time_str)
    if time_match:
        time_part = time_match.group(1)
        for fmt in ("%H:%M", "%I:%M"):
            try:
                t = datetime.strptime(time_part, fmt)
                return base.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)
            except ValueError:
                continue

    if "in " in time_str:
        match = re.search(r'in\s+(\d+)\s*(hour|minute|min|day|week)s?', time_str)
        if match:
            num = int(match.group(1))
            unit = match.group(2).lower()
            if "hour" in unit:
                return now + timedelta(hours=num)
            elif "minute" in unit or "min" in unit:
                return now + timedelta(minutes=num)
            elif "day" in unit:
                return now + timedelta(days=num)
            elif "week" in unit:
                return now + timedelta(weeks=num)

    return None

def _parse_recurring(query):
    query_lower = query.lower()
    if "daily" in query_lower or "every day" in query_lower:
        return "daily"
    if "weekly" in query_lower or "every week" in query_lower:
        return "weekly"
    return None

def _extract_message(query):
    msg = query.lower()
    for word in ["remind me to ", "set a reminder of ", "set a reminder for ",
                 "reminder of ", "reminder for ", "remind me about ",
                 "set reminder ", "set reminder of ", "set reminder for "]:
        if word in msg:
            msg = msg.split(word, 1)[1]
            break
    for word in [" at ", " by ", " in ", " tomorrow", " today", " daily",
                 " weekly", " every day", " every week"]:
        idx = msg.find(word)
        if idx > 0:
            msg = msg[:idx]
            break
    return msg.strip() or "reminder"

def add_reminder(query):
    message = _extract_message(query)
    recurring = _parse_recurring(query)
    reminder_time = _parse_time(query)

    if not reminder_time:
        return False, "I couldn't understand the time. Try saying 'at 8am' or 'in 2 hours'."

    if recurring and reminder_time < datetime.now():
        if recurring == "daily":
            while reminder_time < datetime.now():
                reminder_time += timedelta(days=1)
        elif recurring == "weekly":
            while reminder_time < datetime.now():
                reminder_time += timedelta(weeks=1)

    if not recurring and reminder_time < datetime.now():
        return False, "That time has already passed, sir."

    reminder = {
        "id": str(uuid.uuid4())[:8],
        "message": message,
        "time": reminder_time.isoformat(),
        "created": datetime.now().isoformat(),
        "recurring": recurring,
        "notified": False
    }

    reminders = _load()
    reminders.append(reminder)
    _save(reminders)

    time_label = reminder_time.strftime("%I:%M %p on %B %d")
    if recurring:
        return True, f"Reminder set: '{message}' {recurring} at {reminder_time.strftime('%I:%M %p')}."
    return True, f"Reminder set: '{message}' at {time_label}."

def list_reminders():
    reminders = _load()
    active = [r for r in reminders if not r.get("notified")]
    if not active:
        return "No active reminders, sir."
    lines = ["Active reminders:"]
    for r in active:
        t = datetime.fromisoformat(r["time"])
        recurring = f" ({r['recurring']})" if r.get("recurring") else ""
        lines.append(f"- '{r['message']}' at {t.strftime('%I:%M %p on %B %d')}{recurring}")
    return "\n".join(lines)

def cancel_reminder(query):
    reminders = _load()
    query_lower = query.lower()
    keywords = query_lower.replace("cancel ", "").replace("delete ", "").replace("remove ", "")
    keywords = keywords.replace("reminder ", "").replace("reminders ", "").strip()

    before = len(reminders)
    reminders = [r for r in reminders if keywords not in r["message"].lower()]

    if len(reminders) == before:
        return False, "I couldn't find a matching reminder, sir."

    _save(reminders)
    return True, f"Reminder '{keywords}' cancelled."

def check_reminders():
    now = datetime.now()
    reminders = _load()
    due = []

    for r in reminders:
        try:
            reminder_time = datetime.fromisoformat(r["time"])
        except (ValueError, KeyError):
            continue

        if r.get("notified") and not r.get("recurring"):
            continue

        if now >= reminder_time:
            due.append(r)

    return due

def mark_notified(reminder_id):
    reminders = _load()
    for r in reminders:
        if r["id"] == reminder_id:
            if r.get("recurring"):
                if r["recurring"] == "daily":
                    next_time = datetime.fromisoformat(r["time"]) + timedelta(days=1)
                elif r["recurring"] == "weekly":
                    next_time = datetime.fromisoformat(r["time"]) + timedelta(weeks=1)
                else:
                    next_time = datetime.fromisoformat(r["time"]) + timedelta(days=1)
                r["time"] = next_time.isoformat()
                r["notified"] = False
            else:
                r["notified"] = True
            break
    _save(reminders)

def delete_reminder(reminder_id):
    reminders = _load()
    reminders = [r for r in reminders if r["id"] != reminder_id]
    _save(reminders)
