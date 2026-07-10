import re
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import os
import pymysql
from config import DB_CONFIG

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


# city = ['bratislava','presov','kosice','trnava','zilina','nitra','trencin', 'banska-bystrica','poprad']

pages = {
    'bratislava': 'https://reality.bazos.sk/?hledat=&rubriky=reality&hlokalita=81101&humkreis=10&cenaod=&cenado=1300&Submit=H%C4%BEada%C5%A5&order=&crp=&kitx=ano',
    'presov': 'https://reality.bazos.sk/prenajmu/byt/?hledat=&hlokalita=8001&humkreis=25&cenaod=0&cenado=1300&order=',
    'kosice': 'https://reality.bazos.sk/prenajmu/byt/?hledat=&rubriky=reality&hlokalita=kosice&humkreis=25&cenaod=0&cenado=1300&Submit=H%C4%BEada%C5%A5&order=&crp=&kitx=ano',
    'trnava': 'https://reality.bazos.sk/prenajmu/byt/?hledat=&rubriky=reality&hlokalita=trnava&humkreis=25&cenaod=0&cenado=1300&Submit=H%C4%BEada%C5%A5&order=&crp=&kitx=ano',
    'zilina': 'https://reality.bazos.sk/prenajmu/byt/?hledat=&rubriky=reality&hlokalita=ZILINA&humkreis=25&cenaod=0&cenado=1300&Submit=H%C4%BEada%C5%A5&order=&crp=&kitx=ano',
    'nitra': 'https://reality.bazos.sk/prenajmu/byt/?hledat=&rubriky=reality&hlokalita=NITRA&humkreis=25&cenaod=0&cenado=1300&Submit=H%C4%BEada%C5%A5&order=&crp=&kitx=ano',
    'trencin': 'https://reality.bazos.sk/prenajmu/byt/?hledat=&rubriky=reality&hlokalita=TRENCIN&humkreis=25&cenaod=0&cenado=1300&Submit=H%C4%BEada%C5%A5&order=&crp=&kitx=ano',
    'banska_bistrica': 'https://reality.bazos.sk/prenajmu/byt/?hledat=&rubriky=reality&hlokalita=97401&humkreis=25&cenaod=0&cenado=1300&order=&crp=&kitx=ano',
    'poprad': 'https://reality.bazos.sk/prenajmu/byt/?hledat=&rubriky=reality&hlokalita=POPRAD&humkreis=25&cenaod=0&cenado=1300&Submit=H%C4%BEada%C5%A5&order=&crp=&kitx=ano'
}


def save_listing(data):
    print("SAVE_LISTING_CALLED")
    conn = pymysql.connect(**DB_CONFIG)

    try:
        with conn.cursor() as cursor:
            print(f"SAVE {data['city']} {data['external_id']}")
            cursor.execute(
                 """
                    INSERT IGNORE INTO bazos 
                    (bazos_id, source_url, type, text, price, city, image_url, created_at, category, rooms)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    data['external_id'],
                    data['source_url'],
                    data['type'], #
                    data['description'],
                    data['price'],
                    data['city'],
                    data['image_url'],
                    data['created_at'], #
                    data['category'], #
                    data['rooms'], #
                )

             )
            print(f"DONE {data['city']} {data['external_id']}")
            if cursor.rowcount == 1:
                print(f"INSERTED {data['external_id']}")
            else:
                print(f"SKIPPED {data['external_id']}")
        conn.commit()
    except Exception as e:
        print(f"DB ERROR: {e}")
    finally:
        conn.close()

def extract_external_id(url):
    """
    https://reality.bazos.sk/inzerat/179999999/...
    -> 179999999
    """
    match = re.search(r'/inzerat/(\d+)/', url)
    return match.group(1) if match else None

def extract_rooms(text):
    if not text:
        return None

    text = text.lower()

    # garsonky
    if re.search(r'\bgars[oó]nk', text):
        return 1

    if re.search(r'\bgarzonk', text):
        return 1

    # словесные варианты
    word_patterns = {
        r'\bjednoizb': 1,
        r'\bdvojizb': 2,
        r'\btrojizb': 3,
        r'\bštvorizb': 4,
        r'\bstvorizb': 4,
        r'\bpäťizb': 5,
        r'\bpatizb': 5,
    }

    for pattern, rooms in word_patterns.items():
        if re.search(pattern, text):
            return rooms

    # числовые варианты
    patterns = [
        r'(\d+(?:\.\d+)?)\s*-\s*bedroom',   # 1.5-bedroom
        r'(\d+(?:\.\d+)?)\s*bedroom',       # 1.5 bedroom

        r'(\d+)\s*-\s*izb',                 # 2-izbový
        r'(\d+)\s*[–—-]\s*izb',             # 2–izbový
        r'(\d+)\s*\.\s*izb',                # 2.izbový
        r'(\d+)\s*izbov',                   # 2 izbový
        r'(\d+)\s*izb',                     # 2 izb

        r'(\d+)\s*i\b',                     # 2i
        r'(\d+)\+kk',                       # 2+kk
        r'(\d+)\+1',                        # 1+1

        r'(\d+)\s*room',                    # 2 room
        r'(\d+)\s*-\s*room',                # 2-room
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            try:
                value = float(match.group(1))

                # 1.5-bedroom -> 2 комнаты
                if value % 1:
                    return round(value)

                return int(value)

            except Exception:
                pass

    return None


def parse_city(city, url):
    print(f"START {city}")
    response = requests.get(url, headers=HEADERS, timeout=20)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    items = soup.select(".inzeraty.inzeratyflex")
    print(f"{city}: found {len(items)}")

    session = requests.Session()
    session.headers.update(HEADERS)

    new_count = 0

    for item in items:

        link = item.select_one("h2.nadpis a")

        if not link:
            continue

        source_url = link["href"]

        if source_url.startswith("/"):
            source_url = "https://reality.bazos.sk" + source_url

        external_id = extract_external_id(source_url)

        if not external_id:
            continue

        description_el = item.select_one(".popis")
        description = description_el.get_text(" ", strip=True) if description_el else ""

        if 'reality.bazos.sk' in source_url:
            caseType = 'rent'
            rooms = extract_rooms(description)
            category = None
        else:
            caseType = 'sell_category'
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
                image_url = "https://reality.bazos.sk" + image_url

        data = {
            "source": "bazos",
            "external_id": external_id,
            "source_url": source_url,
            'type': caseType,
            "description": description,
            "price": price,
            "city": city,
            "image_url": image_url,
            'created_at': datetime.now().strftime('%Y-%m-%d'),
            'category': category,
            'rooms': rooms
        }

        save_listing(data)

        new_count += 1

    print(f"[{city}] +{new_count} new")

def main():
    for city, url in pages.items():
        parse_city(city, url)


if __name__ == "__main__":
    main()