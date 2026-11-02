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
    """One line per event. The currency is shown in the section header, not here."""
    fmt = "%a %d %b %H:%M" if with_day else "%H:%M"
    title = html.escape(event.get("title", ""))
    return f"🔴 <b>{local_dt.strftime(fmt)}</b> - {title}"


def group_by_currency(events):
    """Group (local_datetime, event) pairs by currency.

    Events arrive sorted by time, so currencies appear in the order of their first event.
    """
    groups = {}
    for local_dt, event in events:
        currency = event.get("country") or "OTHER"
        groups.setdefault(currency, []).append((local_dt, event))
    return groups


def build_report(title, events, with_day=False):
    """Build the Telegram message with one section per currency (AUD:, USD:, ...)."""
    lines = [f"<b>{title}</b>:\n"]
    for currency, items in group_by_currency(events).items():
        lines.append(f"<b>{html.escape(currency)}:</b>")
        lines += [format_event(dt, e, with_day) for dt, e in items]
        lines.append("")  # blank line between currencies
    return "\n".join(lines).rstrip()


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
        message = build_report(
            "📅 Weekly Forex Report (Red Folder News)", events, with_day=True
        )
    else:  # Daily report (today's news)
        todays = [(dt, e) for dt, e in events if dt.date() == now.date()]
        if not todays:
            print("No high-impact news for today.")
            send_telegram_message("✅ No high-impact news today.")
            return
        message = build_report("🚨 High-Impact News (Today)", todays)

    send_telegram_message(message)
    print("Script executed successfully!")


if __name__ == "__main__":
    main()
