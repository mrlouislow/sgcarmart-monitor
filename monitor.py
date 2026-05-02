import json
import os
import requests
from playwright.sync_api import sync_playwright

# ─── CONFIG (GitHub Secrets) ──────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID   = os.environ["TELEGRAM_CHAT_ID"]
GIST_TOKEN         = os.environ["GIST_TOKEN"]
GIST_ID            = os.environ["GIST_ID"]
VENDOR_URL         = "https://www.sgcarmart.com/used-cars/listing?dl=2984"
GIST_FILENAME      = "seen_cars.json"
# ──────────────────────────────────────────────────────────────────────────────

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
    cars, seen_ids = [], set()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="en-SG",
            timezone_id="Asia/Singapore",
        )
        page = context.new_page()

        # visit homepage first to get cookies
        page.goto("https://www.sgcarmart.com", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2000)

        # now visit the vendor listing
        page.goto(VENDOR_URL, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)

        # debug: print page title and a snippet of HTML
        print(f"Page title: {page.title()}")
        html = page.content()
        print(f"HTML snippet:\n{html[:3000]}")

        # extract all car links
        anchors = page.query_selector_all("a[href*='/used-cars/info.php?ID=']")
        for a in anchors:
            href   = a.get_attribute("href") or ""
            title  = (a.inner_text() or "").strip()
            car_id = href.split("ID=")[-1].split("&")[0]
            if car_id and title and car_id not in seen_ids:
                seen_ids.add(car_id)
                cars.append({
                    "id":    car_id,
                    "title": title,
                    "url":   f"https://www.sgcarmart.com{href}" if href.startswith("/") else href,
                })

        browser.close()
    return cars

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    r = requests.post(url, json={
        "chat_id":    TELEGRAM_CHAT_ID,
        "text":       message,
        "parse_mode": "HTML",
    }, timeout=10)
    if not r.ok:
        print(f"Telegram error {r.status_code}: {r.text}")
    r.raise_for_status()

def main():
    print("Fetching listings with Playwright...")
    listings = fetch_listings()
    print(f"Found {len(listings)} listings on page.")

    try:
        seen_ids = load_seen()
        print(f"Loaded {len(seen_ids)} previously seen IDs from Gist.")
    except Exception as e:
        print(f"Could not load seen IDs ({e}), treating as first run.")
        seen_ids = set()

    new_cars = [c for c in listings if c["id"] not in seen_ids]

    if not seen_ids:
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
