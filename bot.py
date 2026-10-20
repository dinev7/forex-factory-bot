# /// script
# requires-python = ">=3.10"
# dependencies = ["requests", "python-dotenv", "tzdata"]
# ///
import html
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv

# Load environment variables from a .env file (ignored if it doesn't exist)
load_dotenv()

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# Public URL of the weekly Forex Factory calendar in JSON format
FF_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"

# Handles winter/summer time (CET/CEST) automatically
LOCAL_TZ = ZoneInfo("Europe/Madrid")


def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
    }
    response = requests.post(url, json=payload, timeout=15)
    if not response.ok:
        raise RuntimeError(f"Telegram error {response.status_code}: {response.text}")


def get_high_impact_events():
    """Return this week's High-impact events as (local_datetime, event), sorted by time."""
    response = requests.get(FF_URL, timeout=15)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, list):
        raise ValueError(f"Unexpected response from Forex Factory: {str(data)[:200]}")  # noqa: TRY004

    events = []
    for e in data:
        if e.get("impact") != "High":  # 'High' -> Red Folder
            continue
        try:
            # The feed includes a UTC offset, so we can convert to our timezone
            local_dt = datetime.fromisoformat(e["date"]).astimezone(LOCAL_TZ)
        except (KeyError, ValueError):
            continue
        events.append((local_dt, e))

    return sorted(events, key=lambda item: item[0])


def format_event(local_dt, event, with_day=False):
    fmt = "%a %d %b %H:%M" if with_day else "%H:%M"
    title = html.escape(event.get("title", ""))
    country = html.escape(event.get("country", ""))
    return f"🔴 <b>{local_dt.strftime(fmt)}</b> - {title} ({country})"


def main():
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        sys.exit("Missing TELEGRAM_TOKEN or TELEGRAM_CHAT_ID environment variables.")

    try:
        events = get_high_impact_events()
    except (requests.RequestException, ValueError) as e:
        print(f"Error connecting to Forex Factory: {e}")
        sys.exit(1)

    now = datetime.now(LOCAL_TZ)

    if now.weekday() == 6:  # Sunday -> report for the whole week
        if not events:
            print("No high-impact news found for this week.")
            return
        lines = ["📅 <b>Weekly Forex Report (Red Folder News)</b>:\n"]
        lines += [format_event(dt, e, with_day=True) for dt, e in events]
    else:  # Daily report (today's news)
        todays = [(dt, e) for dt, e in events if dt.date() == now.date()]
        if not todays:
            print("No high-impact news for today.")
            send_telegram_message("✅ No high-impact news today.")
            return
        lines = ["🚨 <b>High-Impact News (Today)</b>:\n"]
        lines += [format_event(dt, e) for dt, e in todays]

    send_telegram_message("\n".join(lines))
    print("Script executed successfully!")


if __name__ == "__main__":
    main()
