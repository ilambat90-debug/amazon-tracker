import json
import time
import random
import os
import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
log = logging.getLogger(__name__)

CONFIG_FILE = "sellers.json"
SEEN_FILE = "seen_asins.json"
CHECK_INTERVAL = 3600  # 60 minutes

DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")
DISCORD_CHANNEL_ID = os.environ.get("DISCORD_CHANNEL_ID", "")

BASE_URL = "https://www.amazon.co.uk/s?me={seller_id}&page={page}"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
]

def load_config():
    if not os.path.exists(CONFIG_FILE):
        save_json(CONFIG_FILE, {"sellers": []})
    return load_json(CONFIG_FILE)

def load_json(path):
    with open(path, "r") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def load_seen():
    if not os.path.exists(SEEN_FILE):
        return {}
    return load_json(SEEN_FILE)

def save_seen(seen):
    save_json(SEEN_FILE, seen)

def get_session():
    session = requests.Session()
    ua = random.choice(USER_AGENTS)
    session.headers.update({
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-GB,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
        "DNT": "1",
    })
    # Set UK locale cookies so Amazon serves UK content even from US servers
    session.cookies.set("i18n-prefs", "GBP", domain="www.amazon.co.uk")
    session.cookies.set("sp-cdn", "L5Z9:GB", domain="www.amazon.co.uk")
    session.cookies.set("lc-acbuk", "en_GB", domain="www.amazon.co.uk")
    return session

def parse_products(soup):
    products = []
    # Try multiple selectors Amazon uses
    items = (
        soup.select('div[data-asin][data-component-type="s-search-result"]') or
        soup.select('div[data-asin]')
    )

    for item in items:
        asin = item.get("data-asin", "").strip()
        if not asin or len(asin) != 10:
            continue

        title_el = (
            item.select_one("h2 a span") or
            item.select_one("h2 span") or
            item.select_one(".a-size-medium.a-color-base.a-text-normal") or
            item.select_one(".a-size-base-plus.a-color-base.a-text-normal") or
            item.select_one("[data-cy='title-recipe'] span")
        )
        title = title_el.get_text(strip=True) if title_el else "Unknown Title"

        price_el = item.select_one(".a-price .a-offscreen")
        price = price_el.get_text(strip=True) if price_el else "N/A"

        img_el = item.select_one("img.s-image")
        image = img_el.get("src", "") if img_el else ""

        link = f"https://www.amazon.co.uk/dp/{asin}"

        products.append({
            "asin": asin,
            "title": title,
            "price": price,
            "image": image,
            "link": link,
        })

    return products

def has_next_page(soup):
    return soup.select_one("a.s-pagination-next:not(.s-pagination-disabled)") is not None

def fetch_page(session, seller_id, seller_name, page):
    url = BASE_URL.format(seller_id=seller_id, page=page)
    max_retries = 3

    for attempt in range(max_retries):
        try:
            delay = random.uniform(8, 20)
            log.info(f"[{seller_name}] Page {page} — waiting {delay:.1f}s...")
            time.sleep(delay)

            resp = session.get(url, timeout=20)

            if resp.status_code in (503, 202):
                log.warning(f"[{seller_name}] HTTP {resp.status_code} page {page} (attempt {attempt+1}/{max_retries})")
                time.sleep(random.uniform(30, 60))
                continue

            if resp.status_code == 200:
                if "api-services-support@amazon.com" in resp.text or "Type the characters" in resp.text:
                    log.warning(f"[{seller_name}] CAPTCHA page {page} (attempt {attempt+1}/{max_retries})")
                    time.sleep(random.uniform(60, 120))
                    continue

                # Log a snippet to help debug what Amazon is returning
                soup = BeautifulSoup(resp.text, "html.parser")
                result_count_el = soup.select_one(".s-result-count") or soup.select_one("[data-component-type='s-result-info-bar']")
                if result_count_el:
                    log.info(f"[{seller_name}] Amazon says: {result_count_el.get_text(strip=True)[:100]}")
                else:
                    # Check if page has any search results at all
                    no_results = soup.select_one(".s-no-outline") or "no results" in resp.text.lower()
                    if no_results:
                        log.warning(f"[{seller_name}] Amazon returned a no-results page")
                    else:
                        log.info(f"[{seller_name}] Page loaded (no result count found, page length: {len(resp.text)})")

                return soup, True

            log.warning(f"[{seller_name}] HTTP {resp.status_code} page {page}")
            time.sleep(random.uniform(15, 30))

        except Exception as e:
            log.error(f"[{seller_name}] Error page {page} attempt {attempt+1}: {e}")
            time.sleep(random.uniform(10, 25))

    return None, False

def scrape_seller_asins(seller_id, seller_name):
    all_products = []
    seen_asins = set()

    session = get_session()
    try:
        log.info(f"[{seller_name}] Pre-visiting Amazon UK homepage...")
        session.get("https://www.amazon.co.uk", timeout=15)
        time.sleep(random.uniform(3, 6))
    except Exception as e:
        log.warning(f"Homepage pre-visit failed: {e}")

    page = 1
    max_pages = 20

    while page <= max_pages:
        soup, success = fetch_page(session, seller_id, seller_name, page)

        if not success:
            log.error(f"[{seller_name}] Failed page {page} — stopping")
            break

        page_products = parse_products(soup)
        new_on_page = 0
        for p in page_products:
            if p["asin"] not in seen_asins:
                seen_asins.add(p["asin"])
                all_products.append(p)
                new_on_page += 1

        log.info(f"[{seller_name}] Page {page}: {new_on_page} products found")

        if not has_next_page(soup):
            log.info(f"[{seller_name}] No more pages after page {page}")
            break

        page += 1
        time.sleep(random.uniform(5, 12))

    log.info(f"[{seller_name}] Total: {len(all_products)} products across {page} page(s)")
    return all_products


def send_discord_notification(product, seller_name):
    if not DISCORD_BOT_TOKEN or not DISCORD_CHANNEL_ID:
        log.warning("Discord credentials not set — skipping notification")
        return

    try:
        embed = {
            "title": f"New ASIN from {seller_name}",
            "color": 0xFF9900,
            "fields": [
                {"name": "Title", "value": product["title"][:1024], "inline": False},
                {"name": "ASIN", "value": product["asin"], "inline": True},
                {"name": "Price", "value": product["price"], "inline": True},
                {"name": "Link", "value": product["link"], "inline": False},
            ],
            "timestamp": datetime.utcnow().isoformat(),
            "footer": {"text": "Amazon Seller Tracker"},
        }

        if product.get("image"):
            embed["thumbnail"] = {"url": product["image"]}

        msg_resp = requests.post(
            f"https://discord.com/api/v10/channels/{DISCORD_CHANNEL_ID}/messages",
            headers={
                "Authorization": f"Bot {DISCORD_BOT_TOKEN}",
                "Content-Type": "application/json",
            },
            json={"embeds": [embed]},
        )
        msg_resp.raise_for_status()
        log.info(f"Discord notification sent for ASIN {product['asin']}")

    except Exception as e:
        log.error(f"Discord error: {e}")


def run_check():
    config = load_config()
    sellers = config.get("sellers", [])

    if not sellers:
        log.info("No sellers configured.")
        return

    seen = load_seen()
    new_found = 0

    for seller in sellers:
        sid = seller.get("id", "").strip()
        sname = seller.get("name", sid)
        if not sid:
            continue

        products = scrape_seller_asins(sid, sname)
        known = set(seen.get(sid, []))

        for product in products:
            asin = product["asin"]
            if asin not in known:
                log.info(f"[{sname}] New ASIN: {asin} — {product['title'][:60]}")
                send_discord_notification(product, sname)
                known.add(asin)
                new_found += 1
                time.sleep(1)

        seen[sid] = list(known)

    save_seen(seen)
    log.info(f"Check complete. {new_found} new ASINs found across {len(sellers)} sellers.")


def main():
    log.info("=== Amazon Seller Tracker Started ===")
    log.info(f"Checking every {CHECK_INTERVAL // 60} minutes")

    while True:
        run_check()
        log.info("Sleeping until next check...")
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
