import json
import os
import requests
from bs4 import BeautifulSoup
from curl_cffi.requests import Session

# ─── CONFIG ───────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = "YOUR_BOT_TOKEN"
TELEGRAM_CHAT_ID   = "YOUR_CHAT_ID"   # e.g. -1001234567890 for a channel
VENDOR_URL         = "https://www.sgcarmart.com/used-cars/listing?dl=2984"
# ──────────────────────────────────────────────────────────────────────────────

def fetch_listings():
    cars, seen_ids = [], set()
    with Session(impersonate="chrome124") as s:
        s.get("https://www.sgcarmart.com", timeout=30)
        resp = s.get(VENDOR_URL, timeout=30)
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    for a in soup.select("a[href*='/used-cars/info.php?ID=']"):
        href   = a["href"]
        car_id = href.split("ID=")[-1].split("&")[0]
        title  = a.get_text(strip=True)
        if car_id and title and car_id not in seen_ids:
            seen_ids.add(car_id)
            cars.append({
                "title": title,
                "url":   f"https://www.sgcarmart.com{href}" if href.startswith("/") else href,
            })
    return cars

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    r = requests.post(url, json={
        "chat_id":    TELEGRAM_CHAT_ID,
        "text":       message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }, timeout=10)
    if not r.ok:
        print(f"Telegram error {r.status_code}: {r.text}")
    r.raise_for_status()

def main():
    print("Fetching listings...")
    try:
        listings = fetch_listings()
    except Exception as e:
        print(f"Failed to fetch listings: {e}")
        send_telegram(f"⚠️ SGCarMart monitor failed to fetch listings.\nError: {e}")
        return

    print(f"Found {len(listings)} listings.")

    if not listings:
        send_telegram("⚠️ No listings found for this vendor. The page may have changed.")
        return

    # Send header message
    send_telegram(f"🚗 <b>SGCarMart Vendor Update</b>\n{len(listings)} listing(s) currently available:")

    # Send each car as an individual message
    for i, car in enumerate(listings, 1):
        msg = f"{i}. {car['title']}\n<a href=\"{car['url']}\">View listing</a>"
        send_telegram(msg)

if __name__ == "__main__":
    main()
