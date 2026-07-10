from telethon.tl.types import PhotoSize
from db import cursor
import re
import emoji
from rapidfuzz import fuzz

from collections import Counter

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

def remove_emoji(text):
    return emoji.replace_emoji(text, replace='')

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


def remove_words(text):
    result = re.sub(
        r'^(?:код\s+(?:квартиры|квартири|дома)):\s*\S+\s*|#nr.*|\*\*|^#\w+\s*',
        '',
        text,
        flags=re.DOTALL | re.IGNORECASE
    )

    result = re.sub(
        r'\b(?:аренда|просторная|сдаётся)\b',
        '',
        result,
        flags=re.IGNORECASE
    ).strip()

    return result

def normalization_text(text: str) -> str:
    if not text:
        return ""

    text = normalize_dashes(text.lower())
    # text = remove_words(text)

    # Удаляем служебные префиксы и коды
    #text = re.sub(
    #    r'^код квартир[ыи]:\s*\S+\s*|#nr.*|\*\*|^#\w+\s*',
    #    '',
    #    text,
    #    flags=re.DOTALL | re.IGNORECASE
    #)

    ## Удаляем артикулы вида ba123, ke456 и т.п.
    #text = re.sub(
    #    r'^\s*[a-z]{1,5}\d+\s*',
    #    '',
    #    text,
    #    flags=re.IGNORECASE
    #)

    # Удаляем тип жилья studio / garsonka и т.д.
    #text = re.sub(
    #    r'\b(garsonka|garsónka|garzonka|studio)\b',
    #    ' ',
    #    text,
    #    flags=re.IGNORECASE
    #)

    # Удаляем обозначения комнатности (1i, 2-izbový, 3kk и т.п.)
    #for pattern in ROOM_PATTERNS:
    #    text = re.sub(
    #        pattern,
    #        ' ',
    #        text,
    #        flags=re.IGNORECASE
    #    )

    # Удаляем слова "квартира", "byt", "apartment" и т.д.
    #text = re.sub(
    #    r"""
    #    \b(
    #        квартира|квартиру|квартиры|
    #        byt|bytu|
    #        apartment|apartmán|
    #        room|bedroom
    #    )\b
    #    """,
    #    ' ',
    #    text,
    #    flags=re.IGNORECASE | re.VERBOSE
    #)

    # Удаляем маркетинговые слова
    #text = re.sub(
    #    r'\b(?:аренда|просторная|сдаётся)\b',
    #    ' ',
    #    text,
    #    flags=re.IGNORECASE
    #)

    # Удаляем разделители
    #text = re.sub(r"[|•·\-–—]+", " ", text)

    # Нормализуем пробелы
    #text = re.sub(r"\s+", " ", text)

    return text.strip()

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

def pick_size(sizes):
    # Выбирает подходящий размер thumbnail.
    # Сначала пробуем medium, если его нет — small.
    medium, small = [], []
    for s in sizes or []:
        if isinstance(s, PhotoSize) and hasattr(s, "w"):
            if 300 <= s.w <= 700:
                medium.append(s)
            elif s.w < 300:
                small.append(s)

    if medium:
        return max(medium, key=lambda x: x.w), "medium"
    if small:
        return max(small, key=lambda x: x.w), "small"
    return None, None

def check_hash(photo_hash: str) -> bool:
    # Проверяет, есть ли уже такой хэш изображения в таблице hashes.
    # Если хэш найден, фото считается дубликатом.
    if not photo_hash:
        return True
    cursor.execute("SELECT 1 FROM hashes WHERE photo_hash = %s LIMIT 1", (photo_hash,))
    return cursor.fetchone() is None

def word_set(text: str) -> set[str]:
    return set(text.split())

def ngrams(text: str, n: int = 3) -> set[str]:
    text = re.sub(r"\s+", " ", text.strip())
    if len(text) < n:
        return {text} if text else set()
    return {text[i:i+n] for i in range(len(text) - n + 1)}

def jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0

def text_similarity_score(text1: str, text2: str) -> float:
    """
    text1 и text2 уже должны быть очищены и нормализованы заранее
    Возвращает число 0..1
    """
    if not text1 or not text2:
        return 0.0

    if text1 == text2:
        return 1.0

    ratio = fuzz.ratio(text1, text2) / 100.0
    partial = fuzz.partial_ratio(text1, text2) / 100.0
    token_sort = fuzz.token_sort_ratio(text1, text2) / 100.0
    token_set = fuzz.token_set_ratio(text1, text2) / 100.0

    words1 = word_set(text1)
    words2 = word_set(text2)
    word_jaccard = jaccard(words1, words2)

    grams1 = ngrams(text1, 3)
    grams2 = ngrams(text2, 3)
    char_jaccard = jaccard(grams1, grams2)

    prefix_bonus = 0.0
    if text1[:80] and text1[:80] == text2[:80]:
        prefix_bonus = 0.05

    len1 = len(text1)
    len2 = len(text2)
    len_ratio = min(len1, len2) / max(len1, len2) if max(len1, len2) else 0.0

    score = (
        0.20 * ratio +
        0.15 * partial +
        0.20 * token_sort +
        0.20 * token_set +
        0.10 * word_jaccard +
        0.10 * char_jaccard +
        0.05 * len_ratio +
        prefix_bonus
    )

    return min(score, 1.0)

def find_best_text_match(cursor, text: str, cursorType: str, limit: int = 1000):
    cursor.execute(f"""
        SELECT id, user_id, text, photo_hash
        FROM {cursorType}
        WHERE text IS NOT NULL
          AND text <> ''
        ORDER BY id DESC
        LIMIT %s
    """, (limit,))

    rows = cursor.fetchall()
    if not rows:
        return None

    best = None
    best_score = 0.0

    for row in rows:
        db_text = normalization_text(row["text"])
        score = text_similarity_score(text, db_text)

        if score > best_score:
            best_score = score
            best = {
                "listing_id": row["id"],
                "user_id": row["user_id"],
                "photo_hash": row["photo_hash"],
                "text_score": score,
            }

    return best


def is_bad_text(text: str) -> bool:
    if not text:
        return True

    text = text.lower().strip()

    # слишком короткий
    if len(text) <= 2:
        return True

    # ааааааа / !!!!!!
    if re.search(r"(.)\1{5,}", text):
        return True

    # слишком много спецсимволов
    special = len(re.findall(r"[^a-zа-яёіїєґ0-9\s]", text, re.IGNORECASE))
    if special / max(len(text), 1) > 0.4:
        return True

    # продам продам продам
    words = text.split()

    if len(words) >= 4:
        common_ratio = Counter(words).most_common(1)[0][1] / len(words)

        if common_ratio > 0.6:
            return True

    # слишком много одного символа
    chars = [c for c in text if not c.isspace()]

    if chars:
        ratio = Counter(chars).most_common(1)[0][1] / len(chars)

        if ratio > 0.5:
            return True

    return False

def score_text(cursor, text: str, cursorType: str, user_id: int | None = None, photo_hash: str | None = None):
    """
    Главная функция:
    - ищет лучший текстовый матч в БД
    - проверяет same_user / same_photo
    - возвращает итоговое решение
    """
    best_match = find_best_text_match(cursor, text, cursorType, limit=1000)

    if not best_match:
        return {
            "matched_listing_id": None,
            "text_score": 0.0,
            "same_user": False,
            "same_photo": False,
            "total_score": 0.0,
            "decision": "ok",
        }

    text_score = best_match["text_score"]
    same_user = (
            user_id is not None
            and best_match["user_id"] is not None
            and str(best_match["user_id"]) == str(user_id)
    )
    same_photo = (
        bool(photo_hash) and
        bool(best_match["photo_hash"]) and
        photo_hash == best_match["photo_hash"]
    )

    total_score = text_score

    if same_user:
        total_score += 0.20

    if same_photo:
        total_score += 0.30

    if total_score > 1.0:
        total_score = 1.0

    text_len = len(text.strip())
    word_count = len(text.strip().split())

    is_short_text = text_len <= 20 or word_count <= 3



    if same_photo:
        decision = "duplicate"

    elif is_bad_text(text) == True:
        decision = "bad_text"

    elif is_short_text:
        if same_user and text_score >= 0.97:
            decision = "duplicate"
        else:
            decision = "ok"

    else:
        if same_user and text_score >= 0.92:
            decision = "duplicate"
        elif text_score >= 0.97:
            decision = "review"
        elif text_score >= 0.88 and same_user:
            decision = "review"
        else:
            decision = "ok"

    return {
        "matched_listing_id": best_match["listing_id"],
        "text_score": round(text_score, 4),
        "same_user": same_user,
        "same_photo": same_photo,
        "total_score": round(total_score, 4),
        "decision": decision,
    }