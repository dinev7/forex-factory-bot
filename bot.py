"""These are all the libraries we will be using.
HTML will be used for when we extract the text from the web, html will convert it in order Telegram will understand it
The os import allows Python to interactuate with our operative system (os)
The sys import allows Python to use variables and functions by its' interpreter
The datetime is a library that allows to use Time code
The zoneinfo allows Python to know the OS time zone.

The import requests is used to work with HTTP requests (get, post...) and APIs
the dotenv allows an access to the secret file so we can get information to work with
"""

import html
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv

# Load environment variables from a .env file (ignored if it doesn't exist)
load_dotenv()

# The telegram token is protected in the .env file, because the code is out for the public. The token serves as a "password" to access the bot
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
# The chat ID is the identification of the user's chat so the bot knows where to send messages to
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# Public URL of the weekly Forex Factory calendar specifically in JSON format because of its' structured data formating
FF_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"

# Handles winter/summer time (CET/CEST) automatically. We save it to LOCAL_TZ variable
LOCAL_TZ = ZoneInfo("Europe/Madrid")


# This function allows the bot to send messages to the user (me) when he gets the call to do so
def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
    }
    response = requests.post(url, json=payload, timeout=15)
    # If there was no response by 15s, there is a timeout and the bot will through an error
    if not response.ok:
        raise RuntimeError(f"Telegram error {response.status_code}: {response.text}")


# Function to scrape the news
def get_high_impact_events():
    # Returns this week's High-impact events as (local_datetime, event), sorted by time
    response = requests.get(FF_URL, timeout=15)
    # Raise for status acts as an error-checking guard dog for your web request. 200 -> successful (stays quiet), 404 -> not found, 500/503-> Server Error
    response.raise_for_status()
    data = response.json()
    # Isinstance checks whether data is a list, if not it executes the following.
    if not isinstance(data, list):
        raise ValueError(f"Unexpected response from Forex Factory: {str(data)[:200]}")  # noqa: TRY004

    # Now we filter out the high impact news only, because the json contains many news of the week, specially not relevant ones.
    events = []
    for e in data:
        if e.get("impact") != "High":  # 'High' -> Red Folder
            continue
        # We use try and except because many times the news will have corrupted date fields so try and except will allow to not crash the script
        try:
            # We convert the time to our local time zone
            local_dt = datetime.fromisoformat(e["date"]).astimezone(LOCAL_TZ)
        except (KeyError, ValueError):
            continue
        # This will create a tuple, which means that the date and time of the high impact news cannot be modified otherwise it will throw an error.
        events.append((local_dt, e))
    # Many times the news are not sorted out by time, so this will ensure the right order for us.
    return sorted(events, key=lambda item: item[0])


# This function allows us to view the message in a formated one line text. The with_day is not needed for workdays, it will be only shown in the weekends.
def format_event(local_dt, event, with_day=False):
    # One line per event. The currency is shown in the section header, not on every line
    # a = weekday, d = day of month, b = abrev month name, H = hour, M = min
    fmt = "%a %d %b %H:%M" if with_day else "%H:%M"
    # The escape takes characters that look like HTML code and turns them into safe, harmless plain text so Telegram doesn't get confused
    title = html.escape(event.get("title", ""))
    # strftime -> String Format Time, raw date formats get turned into formatted text string.
    return f"🔴 <b>{local_dt.strftime(fmt)}</b> - {title}"


# This groups all the same currency news into one section in the same message
def group_by_currency(events):
    # Group (local_datetime, event) pairs by currency.

    # Events arrive sorted by time, so currencies appear in the order of their first event.
    # We create a dictionary for the currecies.
    groups = {}
    for local_dt, event in events:
        """ Here even though it is written as country, it refers to the currency, it is just the way forex factory calls it.
        Other is used in case that there's some unknown currency, the script will not crash out.
        """
        currency = event.get("country") or "OTHER"

        """ The (currency, []), allows to check first whether there's already a list created for the currency, otherwise, it will create one with []
        the append drops the event tuple into the list
        """
        groups.setdefault(currency, []).append((local_dt, event))
    return groups


# Takes everything gathered and packages it into a formatted text ready to be sent.
def build_report(title, events, with_day=False):
    # Build the Telegram message with one section per currency (AUD:, USD:, ...)
    # The <b> make the text bold
    lines = [f"<b>{title}</b>:\n"]
    # items extracts both parts of the diccionary, key and value
    for currency, items in group_by_currency(events).items():
        # escape ensures the currency name is safe, append adds it
        lines.append(f"<b>{html.escape(currency)}:</b>")
        lines += [format_event(dt, e, with_day) for dt, e in items]
        lines.append("")  # blank line between currencies
        # glues everything together
    return "\n".join(lines).rstrip()


# Main execution of the script
def main():
    # Checks whether the telegram token and IS exist
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        sys.exit("Missing TELEGRAM_TOKEN or TELEGRAM_CHAT_ID environment variables.")
    # First, it tries to scrape the red flag news
    try:
        events = get_high_impact_events()
    except (requests.RequestException, ValueError) as e:
        print(f"Error connecting to Forex Factory: {e}")
        sys.exit(1)
    # Next, gets the current time, date etc
    now = datetime.now(LOCAL_TZ)
    # If it happened to be Sunday, it will do a whole weekly report, if not, it means it's just not Sunday
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
    # Once everything has been established, the function to send the message is called and sent
    send_telegram_message(message)
    print("Script executed successfully!")


# This stops from other files executing the whole .py instead of a specific function we want from the py
if __name__ == "__main__":
    main()
