from helpers import save_listing, extract_external_id, extract_rooms
from config import HEADERS
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urlparse
import re
from datetime import datetime, timezone

def parse_city(city, url, categoria):
    print(f"START {city} [{categoria}]")

    try:
        response = requests.get(url, headers=HEADERS, timeout=20)
    except requests.RequestException as e:
        print(f"REQUEST ERROR: {url}")
        print(e)
        return

    if not response.text:
        print(f"EMPTY PAGE {url}")
        return

    print(f"STATUS: {response.status_code}")

    base_url = f"{urlparse(url).scheme}://{urlparse(url).netloc}"

    soup = BeautifulSoup(response.text, "html.parser")

    items = soup.select(".inzeraty.inzeratyflex")

    print(f"{city}: found {len(items)}")

    if not items:
        print(f"No listings found: {url}")
        return

    new_count = 0

    for item in items:

        link = item.select_one("h2.nadpis a")

        if not link:
            continue

        source_url = link.get("href")

        if not source_url:
            continue

        if source_url.startswith("/"):
            source_url = base_url + source_url

        external_id = extract_external_id(source_url)

        if not external_id:
            continue

        description_el = item.select_one(".popis")
        description = (
            description_el.get_text(" ", strip=True)
            if description_el
            else ""
        )

        if categoria == "reality":
            case_type = "rent"
            rooms = extract_rooms(description)
        else:
            case_type = "sell"
            rooms = None

        price_el = item.select_one(".inzeratycena")

        price = price_el.get_text(strip=True) if price_el else ""
        price = re.sub(r"[^\d]", "", price)
        price = int(price) if price else None

        image_el = item.select_one("img")

        image_url = None

        if image_el:
            image_url = image_el.get("src")

            if image_url and image_url.startswith("/"):
                image_url = base_url + image_url

        data = {
            "source": "bazos",
            "external_id": external_id,
            "source_url": source_url,
            "type": case_type,
            "description": description,
            "price": price,
            "city": city,
            "image_url": image_url,
            "created_at": datetime.now(timezone.utc),
            "category": categoria,
            "rooms": rooms,
        }

        save_listing(data)

        new_count += 1

    print(f"[{city}] +{new_count} new")