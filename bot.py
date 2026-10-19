import os
from datetime import datetime, timezone, timedelta
import requests
from dotenv import load_dotenv

# Load environment variables from a .env file
load_dotenv()

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")


def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
    }
    requests.post(url, json=payload)


def main():
    # Public URL of the weekly Forex Factory calendar in JSON format
    ff_url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"

    try:
        response = requests.get(ff_url)
        events = response.json()
    except (requests.RequestException, ValueError) as e:
        print(f"Error connecting to Forex Factory: {e}")
        return

    # Define the target timezone (e.g., UTC + 2)
    custom_tz = timezone(timedelta(hours=2))
    now = datetime.now(custom_tz)
    today = now.date()
    day_of_week = now.weekday()  # 0=Monday, 6=Sunday

    # Filter only high-impact news ('High' -> Red Folder)
    red_folder_news = [e for e in events if e.get("impact") == "High"]

    message = ""

    # If it's Sunday (6), prepare the report for the upcoming week
    if day_of_week == 6:
        message = "📅 *Weekly Forex Report (Red Folder News)*:\n\n"
        for event in red_folder_news:
            message += f"🔴 *{event.get('date')}* - {event.get('title')} ({event.get('country')})\n"
    else:
        # Daily report (today's news)
        today_str = today.strftime("%Y-%m-%d")
        todays_news = [e for e in red_folder_news if today_str in e.get("date", "")]

        if not todays_news:
            print("No high-impact news for today (or they have already passed).")
            # Send a test message to confirm the bot is active even if there are no news today
            send_telegram_message("🔥 Test on Telegram MSG: Bot is alive!")
            return

        message = "🚨 *High-Impact News (Today)*:\n\n"
        for event in todays_news:
            time_str = (
                event.get("date", "").split("T")[1][:5]
                if "T" in event.get("date", "")
                else ""
            )
            message += (
                f"🔴 *{time_str}* - {event.get('title')} ({event.get('country')})\n"
            )

    # Send the filtered message to Telegram
    send_telegram_message(message)
    print("Script executed successfully!")


if __name__ == "__main__":
    main()


# Test if the Bot is working by sending a test message to the Telegram chat
send_telegram_message("🔥 Test on Telegram MSG")
