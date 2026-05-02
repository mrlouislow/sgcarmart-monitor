import requests
from bs4 import BeautifulSoup
import json
import os

# ─── CONFIG (set these as GitHub Secrets) ─────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID   = os.environ["TELEGRAM_CHAT_ID"]
GIST_TOKEN         = os.environ["GIST_TOKEN"]       # GitHub PAT with gist scope
GIST_ID            = os.environ["GIST_ID"]           # created once, saved as secret
VENDOR_URL         = "https://www.sgcarmart.com/used-cars/listing?dl=2984"
GIST_FILENAME      = "seen_cars.json"
# ──────────────────────────────────────────────────────────────────────────────

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-SG,en;q=0.9",
}

def load_seen():
    url = f"https://api.github.com/gists/{GIST_ID}"
    r = requests.get(url, headers={"Authorization": f"token {GIST_TOKEN}"}, timeout=10)
    r.raise_for_status()
    content = r.json()["files"][GIST_FILENAME]["content"]
    return set(json.loads(content))

def save_seen(ids):
    url = f"https://api.github.com/gists/{GIST_ID}"
    payload = {"files": {GIST_FILENAME: {"content": json.dumps(list(ids))}}}
    r = requests.patch(url, json=payload,
                       headers={"Authorization": f"token {GIST_TOKEN}"}, timeout=10)
    r.raise_for_status()

def fetch_listings():
    resp = requests.get(VENDOR_URL, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    cars, seen_ids = [], set()
    for a in soup.select("a[href*='/used-cars/info.php?ID=']"):
        href   = a["href"]
        car_id = href.split("ID=")[-1].split("&")[0]
        title  = a.get_text(strip=True)
        if car_id and title and car_id not in seen_ids:
            seen_ids.add(car_id)
            cars.append({
                "id":    car_id,
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
    }, timeout=10)
    r.raise_for_status()

def main():
    print("Fetching listings...")
    listings = fetch_listings()
    print(f"Found {len(listings)} listings on page.")

    try:
        seen_ids = load_seen()
        print(f"Loaded {len(seen_ids)} previously seen IDs from Gist.")
    except Exception as e:
        # First run — Gist exists but may be empty
        print(f"Could not load seen IDs ({e}), treating as first run.")
        seen_ids = set()

    new_cars = [c for c in listings if c["id"] not in seen_ids]

    if not seen_ids:
        # First run — seed silently, send confirmation
        print("First run: seeding baseline, no notifications sent.")
        save_seen({c["id"] for c in listings})
        send_telegram("✅ SGCarMart monitor is <b>live on GitHub Actions</b>!\nYou'll be notified when this vendor posts new cars.")
        return

    if new_cars:
        print(f"{len(new_cars)} new car(s) found!")
        for car in new_cars:
            send_telegram(
                f"🚗 <b>New listing!</b>\n\n"
                f"{car['title']}\n"
                f"<a href=\"{car['url']}\">View on SGCarMart</a>"
            )
        save_seen(seen_ids | {c["id"] for c in new_cars})
    else:
        print("No new listings.")

if __name__ == "__main__":
    main()
