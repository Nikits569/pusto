from config import DB_CONFIG
import pymysql
import re

def save_listing(data):
    print("SAVE_LISTING_CALLED")
    conn = pymysql.connect(**DB_CONFIG)

    try:
        with conn.cursor() as cursor:
            print(f"SAVE {data['city']} {data['external_id']}")
            cursor.execute(
                """
                INSERT IGNORE INTO bazos
                (
                    bazos_id,
                    source_url,
                    type,
                    text_sk,
                    price,
                    city,
                    image_url,
                    created_at,
                    category,
                    rooms
                )
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    data['external_id'],
                    data['source_url'],
                    data['type'],
                    data['description'],
                    data['price'],
                    data['city'],
                    data['image_url'],
                    data['created_at'],
                    data['category'],
                    data['rooms']
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