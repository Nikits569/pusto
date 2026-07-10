import pymysql
import os
import re
import emoji
import math

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "django_user"),
    "password": os.getenv("DB_PASSWORD", "S9!kLm2#pQz8"),
    "database": os.getenv("DB_NAME", "pusto_database"),
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
    "autocommit": False,
}

text_example="""sl6240 дом в центре rovinka 15 мин до bratislava 59 м² новостройка сад терраса парковка во дворе полностью меблирован на заказ qled 4k tv спальня с рабочим уголком гостиная современная кухня индукционная панель, посудомойка, микроволновка стиралка с сушилкой ванная: плитка, сантехника villeroy & boch 6 камерные пластиковые окна внешние жалюзи москитные сетки кондиционер samsung с wi fi тёплый пол интернет + tv включены парковка включена рядом: billa, dm, аптека, фитнес тихая локация, хорошая звукоизоляция для 1 2 человек без животных свободен сейчас : 899 €/мес.

(включены энергии, интернет, tv, парковка) депозит по договоренности комиссия: 100% #vl записаться на просмотр @renteu_bot [подать заявку на подбор ](https://t.me/renteu_bot) [наш канал](https://t.me/rent_slovakia)"""

def remove_emoji(text):
    return emoji.replace_emoji(text, replace='')

#def remove_words(text):
#    result = re.sub(
#        r'^(?:код\s+(?:квартиры|квартири|дома)):\s*\S+\s*|#nr.*|\*\*|^#\w+\s*',
#        '',
#        text,
#        flags=re.DOTALL | re.IGNORECASE
#    )
#
#    result = re.sub(
#        r'\b(?:аренда|просторная|сдаётся)\b',
#        '',
#        result,
#        flags=re.IGNORECASE
#    ).strip()
#
#    return result

ROOM_PATTERNS = [
    r"\b(\d+)\s*-\s*комн(?:\.|атн(?:ая|ый|ое)?)?",
    r"\b(\d+)\s+комн(?:\.|\b)",
    r"\b(\d+)\s*-\s*ком\.",
    r"\b(\d+)\s*-\s*ком\b",

    r"\b(\d+)\s*-\s*к\b",
    r"\b(\d+)к\b",

    r"\b(\d+)\s*-\s*кк\b",
    r"\b(\d+)кк\b",

    r"\b(\d+)кк?вартир",
    r"\b(\d+)\s*квартир",

    r"\b(\d+)\s*-\s*комнат",
    r"\b(\d+)\s+комнат",

    r"\b(\d+)\s*room",
    r"\b(\d+)\s*bedroom",

    r"\b(\d+)\s*izb",
    r"\b(\d+)i\b",
    r"\b(\d+)\+kk\b",
    r"\b(\d+)\+1\b",
]

def normalization_text(text):
    if text is None:
        return ""

    text = text.lower()
    text = remove_emoji(text)
    #text = remove_words(text)

    # убрать ссылки, а не весь текст
    text = re.sub(r'(https?://\S+|www\.\S+|t\.me/\S+|telegram\.me/\S+)', '', text, flags=re.IGNORECASE)
    text = re.sub(
        r'^код квартир[ыи]:\s*\S+\s*|#nr.*|\*\*|^#\w+\s*',
        '',
        text,
        flags=re.DOTALL | re.IGNORECASE
    )

    text = re.sub(r'^[a-zA-Z]{2}\d+\s*', '', text)

    text = re.sub(
        r'\b(?:аренда|просторная|сдаётся)\b',
        '',
        text,
        flags=re.IGNORECASE
    ).strip()

    text = re.sub(r'\s+', ' ', text).strip()
    return text

def normalize_dashes(text: str) -> str:
    return re.sub(
        r"[\u2010\u2011\u2012\u2013\u2014\u2212]",
        "-",
        text
    )

def extract_rooms(text):
    if not text:
        return None

    text = normalize_dashes(text.lower())

    # garsonka = 1 комната
    if re.search(
        r"\b(garsonka|garsónka|garzonka|studio)\b",
        text
    ):
        return 1

    # 1,5-комн. / 2.5 izb / 3,5i
    m = re.search(
        r"\b(\d+[.,]\d+)\s*(?:-|комн|комнат|izb|i\b|кк|к\b)",
        text,
        re.IGNORECASE
    )

    if m:
        return float(m.group(1).replace(",", "."))

    # обычные квартиры
    for pattern in ROOM_PATTERNS:
        m = re.search(pattern, text, re.IGNORECASE)

        if m:
            return int(m.group(1))

    return None




def clean_title(text: str) -> str:
    if not text:
        return ""

    text = normalize_dashes(text.lower())

    text = re.sub(
        r"\b(garsonka|garsónka|garzonka|studio)\b",
        " ",
        text,
        flags=re.IGNORECASE
    )

    for pattern in ROOM_PATTERNS:
        text = re.sub(
            pattern,
            " ",
            text,
            flags=re.IGNORECASE
        )

    text = re.sub(
        r"""
        \b(
            квартира|квартиру|квартиры|
            byt|bytu|
            apartment|apartmán|
            room|bedroom
        )\b
        """,
        " ",
        text,
        flags=re.IGNORECASE | re.VERBOSE
    )

    text = re.sub(r"[|•·\-–—]+", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()

def cleanText(value: str):
    value = value.lower()
    result = re.sub(
        r'^код квартир[ыи]:\s*\S+\s*|#nr.*|\*\*|^#\w+\s*',
        '',
        value,
        flags=re.DOTALL | re.IGNORECASE
    )

    #result = re.sub(
    #    r'^\s*[a-z]{1,5}\d+\s*',
    #    '',
    #    result,
    #    flags=re.IGNORECASE
    #)

    result = re.sub(
        r'\b(?:аренда|просторная|сдаётся)\b',
        '',
        result,
        flags=re.IGNORECASE
    ).strip()

    return result

def parse_price(value):
    return int(re.sub(r'[^\d]', '', value))

def extract_price(text):
    text = text or ""

    MIN_RENT_PRICE = 201

    # Выделяем блок цен после 💶
    price_block_match = re.search(
        r'💶(.*?)(?:🔑|💼|📍|📸|#VL|$)',
        text,
        re.IGNORECASE | re.DOTALL
    )

    price_block = (
        price_block_match.group(1)
        if price_block_match
        else text
    )

    # 1. Ищем месячную аренду (самый приоритетный вариант)
    monthly_patterns = [
        r'(\d[\d ]*)\s*€\s*/\s*мес',
        r'(\d[\d ]*)\s*€\s*/\s*месяц',
        r'(\d[\d ]*)\s*€\s*/\s*month',
        r'(\d[\d ]*)\s*€\s*/\s*mes',
        r'(\d[\d ]*)\s*€\s*mesačne',
        r'(\d[\d ]*)\s*€\s*mesiac',
        r'(\d[\d ]*)\s*€\s*mes\.',
    ]

    for pattern in monthly_patterns:
        matches = re.finditer(
            pattern,
            price_block,
            re.IGNORECASE
        )

        for match in matches:
            price = parse_price(match.group(1))

            if price and price >= MIN_RENT_PRICE:
                return price

    # 2. Ищем итоговые суммы вида:
    # = 1010 €/мес
    totals = re.findall(
        r'=\s*(\d[\d ]*)\s*€',
        price_block,
        re.IGNORECASE
    )

    valid_prices = []

    for x in totals:
        price = parse_price(x)

        if price and price >= MIN_RENT_PRICE:
            valid_prices.append(price)

    if valid_prices:
        return min(valid_prices)

    # 3. Явные ключевые слова
    patterns = [
        r'аренда:\s*(\d[\d ]*)\s*€',
        r'цена:\s*(\d[\d ]*)\s*€',
        r'стоимость:\s*(\d[\d ]*)\s*€',
        r'nájom:\s*(\d[\d ]*)\s*€',
        r'rent:\s*(\d[\d ]*)\s*€',
        r'ціна:\s*(\d[\d ]*)\s*€',
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            price_block,
            re.IGNORECASE
        )

        if match:
            price = parse_price(match.group(1))

            if price and price >= MIN_RENT_PRICE:
                return price

    # 4. Обычные цены, но исключаем парковки и т.п.
    skip_words = [
        'парковка',
        'паркинг',
        'гараж',
        'parkovanie',
        'parking',
        'internet',
        'интернет',
        'wifi',
        'место',
        'гараже',
        'гаражное',
        'parkovacie miesto',
        'подземный гараж',
        'внешнее место',
    ]

    for match in re.finditer(
            r'(\d[\d ]*)\s*€',
            price_block,
            re.IGNORECASE
    ):
        start = max(0, match.start() - 100)
        context = price_block[start:match.start()].lower()

        if any(word in context for word in skip_words):
            continue

        price = parse_price(match.group(1))

        if price and price >= MIN_RENT_PRICE:
            return price

    return None

print(extract_rooms(text_example))
print(extract_price(text_example))



conn = pymysql.connect(**DB_CONFIG)

with conn.cursor() as cursor:
    try:
        cursor.execute(
            'SELECT id, text, title FROM ads_neighborpost'
        )

        posts = cursor.fetchall()

        for post in posts:
            post_id = post["id"]

            rooms = extract_rooms(post["text"] or "")
            value = extract_price(post["text"] or "")
            text = normalization_text(post["text"] or "")

            title = clean_title(remove_emoji(text))[:25]

            text = remove_emoji(text)


            print('rooms', rooms, 'id', post_id)
            if value is not None:

                cursor.execute(
                    """
                    UPDATE ads_neighborpost
                    SET text = %s, title = %s, budget=%s, rooms=%s
                    WHERE id=%s
                    """,
                    (text, title, value, rooms, post_id)
                )

    finally:
        conn.commit()
        cursor.close()
        conn.close()