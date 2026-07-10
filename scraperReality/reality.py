#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Парсер объявлений аренды квартир с reality.sk по списку городов + сохранение в MySQL.

=== ЧТО ДОБАВЛЕНО В ЭТОЙ ВЕРСИИ ===

Раньше данные брались только со страницы списка (карточка объявления):
заголовок, короткое описание, цена, одна главная фотка.

Теперь для КАЖДОГО НОВОГО (ещё не сохранённого в БД по content_hash)
объявления скрипт дополнительно заходит на страницу самого объявления
(https://www.reality.sk/byty/<slug>/<ad_id>/) и вытаскивает:

    1. ПОЛНОЕ описание (блок "Info" целиком, а не обрезанный сниппет).
       Это полное описание пишется в колонку text_sk (отдельной колонки
       full_description в БД НЕТ -- короткий текст со страницы списка
       по-прежнему пишется в колонку text).
    2. Первые 5 фото объявления (скачивает файлы на диск + сохраняет
       ссылки в БД).
    3. Координаты (широта/долгота), если сайт их отдаёт в HTML —
       из JSON-LD, meta-тегов geo.position/ICBM или встроенного JSON
       в <script>.

ВАЖНО: фотогалерея и карта на странице объявления, судя по всему,
подгружаются JS-виджетом (в статическом HTML их может не быть видно
обычным requests). Поэтому extract_gallery_photos() и extract_geo()
написаны с НЕСКОЛЬКИМИ стратегиями-фолбэками и подробно
прокомментированы -- если на реальном сайте что-то не совпадёт,
самое быстрое решение -- открыть DevTools -> Network/Elements на
странице объявления, найти, где реально лежат фото/координаты
(JSON в <script>, отдельный XHR-запрос и т.п.) и поправить эти две
функции under EXTRACT_GALLERY_PHOTOS / EXTRACT_GEO.

=== ИЗМЕНЕНИЯ В СХЕМЕ БД ===

В таблицу reality нужно добавить (ALTER TABLE, см. MIGRATION_SQL ниже):

    latitude            DOUBLE(10,7)    -- широта
    longitude           DOUBLE(10,7)    -- долгота

(Колонка full_description больше НЕ добавляется -- полное описание
пишется в уже существующую колонку text_sk.)

И создать отдельную таблицу для фото (нормальная связь один-ко-многим,
вместо 5 столбцов photo_1..photo_5):

    CREATE TABLE reality_photos (
        photo_id     INT PRIMARY KEY AUTO_INCREMENT,
        reality_id   INT NOT NULL,
        position     TINYINT NOT NULL,          -- 1..5, порядок в галерее
        photo_url    VARCHAR(500),               -- оригинальная ссылка на сайте
        local_path   VARCHAR(500),               -- путь к скачанному файлу на диске
        FOREIGN KEY (reality_id) REFERENCES reality(reality_id) ON DELETE CASCADE,
        UNIQUE KEY uniq_reality_position (reality_id, position)
    );

Готовый SQL лежит в переменной MIGRATION_SQL ниже -- можно выполнить
один раз вручную (или скрипт применит его сам при --migrate).

--- (остальной докстринг из исходной версии, без изменений) ---

Каждое объявление возвращается как dict:
    {
        "ad_id": "Ju1OBxIdt_7",
        "source_url": "https://www.reality.sk/byty/.../",
        "image_url": "https://img.unitedclassifieds.sk/...",
        "text": "заголовок + короткое описание",   # идёт в колонку text
        "price": 550,
        "city": "banska-bystrica",
        "created_at": datetime(...),
        "content_hash": "a3f5...",
        "full_description": "...",     # NEW, идёт в колонку text_sk
        "latitude": 48.1234,            # NEW, может быть None
        "longitude": 17.1234,           # NEW, может быть None
        "photos": [...до 5 ссылок...],  # NEW, не идёт напрямую в reality,
                                          # идёт в reality_photos
    }

Запуск:
    python3 reality_sk_parser.py
    python3 reality_sk_parser.py --pages 0
    python3 reality_sk_parser.py --cities kosice nitra --pages 2
    python3 reality_sk_parser.py --no-details      # старое поведение, без захода на карточку
    python3 reality_sk_parser.py --migrate --no-db  # только применить ALTER/CREATE и выйти

ВАЖНО про cron:
    */15 * * * * /usr/bin/flock -n /tmp/reality_parser.lock \
        /usr/bin/python3 /path/to/reality_sk_parser.py >> /var/log/reality_parser.log 2>&1

ВАЖНО про переменные окружения:
    export DB_PASSWORD="..."
"""

import os
import re
import sys
import json
import time
import hashlib
import logging
import argparse
from datetime import datetime
from config import DB_CONFIG
import requests
import pymysql
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Логирование
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("topReality_sk_parser")


# ---------------------------------------------------------------------------
# Константы
# ---------------------------------------------------------------------------

BASE = "https://www.reality.sk"

CITY = [
    "bratislava", "presov", "kosice", "trnava", "zilina",
    "nitra", "trencin", "banska-bystrica", "poprad",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "sk-SK,sk;q=0.9,en;q=0.8",
}

ROOM_PATTERNS = [
    (r'\bgars[oó]nka\b', 1),
    (r'\bgarzonka\b', 1),
    (r'\bštúdio\b', 1),
    (r'\bstudio\b', 1),
    (r'\b([1-9])\s*[- ]?\s*izbov[ýyiáé]*', None),
    (r'\b([1-9])\s*izb\b', None),
    (r'\b([1-9])\s*i\b', None),
    (r'\b([1-9])\+kk\b', None),
    (r'\b([1-9])\+1\b', None),
]

AD_ID_RE = re.compile(r'-([A-Za-z0-9_]+)$')

# Сколько фото скачивать с карточки объявления
MAX_PHOTOS = 5

# Куда складывать скачанные фото на диске: photos/<ad_id>/1.jpg ...
PHOTOS_DIR = os.getenv("PHOTOS_DIR", "photos")

# Регексы для поиска координат в сыром HTML/JSON, если BeautifulSoup
# по тегам ничего не находит (см. extract_geo)
GEO_JSON_RE = re.compile(
    r'"lat(?:itude)?"\s*:\s*"?(-?\d{1,3}\.\d+)"?\s*,\s*"lon(?:g|gitude)?"\s*:\s*"?(-?\d{1,3}\.\d+)"?',
    re.IGNORECASE,
)
ICBM_RE = re.compile(r'([\-0-9.]+),\s*([\-0-9.]+)')


MIGRATION_SQL = [
    "ALTER TABLE reality ADD COLUMN IF NOT EXISTS latitude DOUBLE(10,7) NULL AFTER city",
    "ALTER TABLE reality ADD COLUMN IF NOT EXISTS longitude DOUBLE(10,7) NULL AFTER latitude",
    """
    CREATE TABLE IF NOT EXISTS reality_photos (
        photo_id     INT PRIMARY KEY AUTO_INCREMENT,
        reality_id   INT NOT NULL,
        position     TINYINT NOT NULL,
        photo_url    VARCHAR(500),
        local_path   VARCHAR(500),
        FOREIGN KEY (reality_id) REFERENCES reality(reality_id) ON DELETE CASCADE,
        UNIQUE KEY uniq_reality_position (reality_id, position)
    )
    """,
]


def _get_db_config() -> dict:
    if not DB_CONFIG:
        log.error("DB_CONFIG не задан в config.py")
        sys.exit(1)
    return DB_CONFIG


def run_migration(db_config: dict):
    """Накатывает ALTER/CREATE из MIGRATION_SQL. Безопасно запускать повторно."""
    conn = pymysql.connect(**db_config)
    try:
        with conn.cursor() as cur:
            for stmt in MIGRATION_SQL:
                try:
                    cur.execute(stmt)
                except Exception as e:
                    # MySQL < 8.0.29 не понимает "ADD COLUMN IF NOT EXISTS" —
                    # в этом случае просто игнорируем "duplicate column" ошибку.
                    if "Duplicate column" in str(e) or "already exists" in str(e):
                        log.info("Уже применено: %s", stmt.strip().splitlines()[0])
                    else:
                        raise
        conn.commit()
        log.info("Миграция схемы применена.")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Утилиты (без изменений)
# ---------------------------------------------------------------------------

def extract_rooms(title: str = "", params: str = "", text: str = ""):
    source = f"{title} {params} {text}".lower()
    for pattern, fixed in ROOM_PATTERNS:
        m = re.search(pattern, source)
        if m:
            if fixed is not None:
                return fixed
            return int(m.group(1))
    return None


def extract_ad_id(slug: str) -> str:
    if not slug:
        return slug
    m = AD_ID_RE.search(slug)
    if m:
        return m.group(1)
    return slug


def build_text(title: str, description: str) -> str:
    title = re.sub(r"\s+", " ", (title or "")).strip()
    description = re.sub(r"\s+", " ", (description or "")).strip()
    if title and description:
        return f"{title} {description}"
    return title or description


def make_content_hash(text: str, price, city: str) -> str:
    normalized_text = re.sub(r"\s+", " ", (text or "").strip().lower())
    raw = f"{normalized_text}|{price}|{(city or '').strip().lower()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# NEW: парсинг страницы конкретного объявления
# ---------------------------------------------------------------------------

def extract_full_description(soup: BeautifulSoup) -> str:
    """
    Полное описание лежит в блоке под заголовком "Info" (див/секция),
    до следующего заголовка "Charakteristika". Текст в HTML присутствует
    целиком (кнопка "Prečítať viac" -- это CSS/JS-раскрытие уже
    имеющегося в DOM текста, а не подгрузка по клику), так что requests
    его видит без эмуляции браузера.

    Стратегия: ищем любой заголовочный тег (h2/h3/div и т.п.), чей текст
    == "Info", берём все параграфы/списки между ним и следующим
    заголовком уровня секции ("Charakteristika" / "Vybavenosť" / и т.п.).

    Результат этой функции при сохранении в БД (см. save_listing) идёт
    в колонку text_sk -- отдельной колонки full_description в БД нет.
    """
    heading = None
    for tag in soup.find_all(["h2", "h3", "h4", "div", "span"]):
        if tag.get_text(strip=True).lower() == "info":
            heading = tag
            break

    if heading is None:
        return ""

    stop_words = {"charakteristika", "vybavenosť v okolí", "nehnuteľnosť na mape"}
    parts = []
    node = heading
    while True:
        node = node.find_next_sibling()
        if node is None:
            break
        node_text = node.get_text(" ", strip=True)
        if node_text.lower() in stop_words:
            break
        if node_text and node_text.lower() != "prečítať viac":
            parts.append(node_text)

    full_text = "\n".join(p for p in parts if p)
    return full_text.strip()


def extract_geo(soup: BeautifulSoup, html: str):
    """
    Пытается достать (latitude, longitude) несколькими способами,
    от самого надёжного к самому "на всякий случай":

    1. JSON-LD (<script type="application/ld+json">) с полем geo /
       latitude / longitude -- частый паттерн у объектов недвижимости
       для SEO (schema.org RealEstateListing / Place).
    2. Meta-теги geo.position / ICBM.
    3. Любой JSON-блок в <script> с ключами lat/lng/latitude/longitude
       (некоторые сайты кладут данные для карты в window.__NUXT__ или
       аналог).

    Если ничего не найдено -- возвращает (None, None). В этом случае
    карту, скорее всего, рисует отдельный JS-виджет, который тянет
    данные отдельным XHR-запросом -- тогда нужно смотреть вкладку
    Network в браузере на странице объявления и добавлять сюда прямой
    запрос к этому API.
    """
    # 1. JSON-LD
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except (ValueError, TypeError):
            continue
        candidates = data if isinstance(data, list) else [data]
        for item in candidates:
            geo = item.get("geo") if isinstance(item, dict) else None
            if isinstance(geo, dict):
                lat = geo.get("latitude")
                lon = geo.get("longitude")
                if lat is not None and lon is not None:
                    try:
                        return float(lat), float(lon)
                    except ValueError:
                        pass

    # 2. Meta-теги
    meta_geo = soup.find("meta", attrs={"name": "geo.position"})
    if meta_geo and meta_geo.get("content"):
        m = ICBM_RE.search(meta_geo["content"])
        if m:
            try:
                return float(m.group(1)), float(m.group(2))
            except ValueError:
                pass

    meta_icbm = soup.find("meta", attrs={"name": "ICBM"})
    if meta_icbm and meta_icbm.get("content"):
        m = ICBM_RE.search(meta_icbm["content"])
        if m:
            try:
                return float(m.group(1)), float(m.group(2))
            except ValueError:
                pass

    # 3. Произвольный JSON внутри <script> с lat/lng
    m = GEO_JSON_RE.search(html)
    if m:
        try:
            return float(m.group(1)), float(m.group(2))
        except ValueError:
            pass

    return None, None


def extract_gallery_photos(soup: BeautifulSoup, base_url: str, limit: int = MAX_PHOTOS):
    """
    Собирает до `limit` ссылок на фото карточки объявления.

    Фото у reality.sk отдаются через CDN img.unitedclassifieds.sk, где
    в пути закодирован (base64) размер/фильтры картинки, например:

        .../MTgwMHgxMzUwL2ZpbHRlcnM6cXVhbGl0eSg4NSk/...   -> "1800x1350/filters:quality(85)"
        .../Zml0LWluLzE3MHgxNzAvZmlsdGVyczpmb3JtYXQod2VicCk/... -> "fit-in/170x170/filters:format(webp)"

    То есть крупные фото объявления -- это "1800x13NN", а маленькие
    170x170 -- аватар агента. Поэтому просто искать <img> недостаточно,
    нужно ещё отфильтровать служебные картинки (лого, аватар, иконки).

    Если галерея на странице подгружается JS-ом отдельным запросом (что
    похоже на правду для этого сайта), здесь просто не найдётся 5 фото --
    тогда стоит посмотреть страницу .../<slug>-foto/<ad_id>/ через
    DevTools -> Network и найти реальный источник данных галереи.
    """
    urls = []
    for img in soup.find_all("img"):
        src = img.get("data-lazy-src") or img.get("data-src") or img.get("src") or ""
        if not src.startswith("http"):
            continue
        if "img.unitedclassifieds.sk" not in src:
            continue
        if "170x170" in src or "logo" in src.lower():
            continue  # аватар агента / служебная картинка
        if src not in urls:
            urls.append(src)
        if len(urls) >= limit:
            break
    return urls


def download_photos(photo_urls, ad_id: str, session: requests.Session):
    """
    Скачивает фото на диск в PHOTOS_DIR/<ad_id>/1.jpg, 2.jpg, ...
    Возвращает список dict {"url":..., "local_path":..., "position":...}.
    Ошибка скачивания одной фотки не должна ронять остальные.
    """
    result = []
    folder = os.path.join(PHOTOS_DIR, ad_id)
    os.makedirs(folder, exist_ok=True)

    for i, url in enumerate(photo_urls, start=1):
        local_path = os.path.join(folder, f"{i}.jpg")
        try:
            resp = session.get(url, headers=HEADERS, timeout=20)
            resp.raise_for_status()
            with open(local_path, "wb") as f:
                f.write(resp.content)
        except requests.RequestException as e:
            log.warning("Не удалось скачать фото %s (%s): %s", i, url, e)
            local_path = None

        result.append({"url": url, "local_path": local_path, "position": i})

    return result


def fetch_detail(url: str, ad_id: str, session: requests.Session, download: bool = True):
    """
    Заходит на страницу объявления и возвращает
    {"full_description": str, "latitude": float|None, "longitude": float|None,
     "photos": [{"url", "local_path", "position"}, ...]}
    "full_description" здесь -- ключ внутреннего словаря Python; при
    сохранении в БД (save_listing) его значение кладётся в колонку
    text_sk (отдельной колонки full_description в БД больше нет).
    Никогда не бросает исключение наружу -- при ошибке возвращает "пустой" результат,
    чтобы одно упавшее объявление не останавливало весь прогон.
    """
    empty = {"full_description": "", "latitude": None, "longitude": None, "photos": []}
    try:
        resp = session.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as e:
        log.warning("Не удалось загрузить карточку объявления %s: %s", url, e)
        return empty

    soup = BeautifulSoup(resp.text, "lxml")

    full_description = extract_full_description(soup)
    latitude, longitude = extract_geo(soup, resp.text)
    photo_urls = extract_gallery_photos(soup, url, MAX_PHOTOS)
    photos = download_photos(photo_urls, ad_id, session) if (download and photo_urls) else (
        [{"url": u, "local_path": None, "position": i} for i, u in enumerate(photo_urls, 1)]
    )

    return {
        "full_description": full_description,
        "latitude": latitude,
        "longitude": longitude,
        "photos": photos,
    }


# ---------------------------------------------------------------------------
# БД
# ---------------------------------------------------------------------------

def save_listing(conn, data: dict) -> str:
    """
    Сохраняет объявление + (если есть) фото в reality_photos.
    Возвращает 'inserted' или 'skipped'.
    """
    rooms = extract_rooms(data.get("title", ""), data.get("params", ""), data.get("text", ""))

    with conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT IGNORE INTO reality
                (ad_id, source_url, text, text_sk, price, image_url,
                 created_at, city, rooms, content_hash,
                 latitude, longitude)
            VALUES
                (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                data["ad_id"],
                data["source_url"],
                data["text"],
                data.get("full_description") or None,  # text_sk -- сюда пишем полное описание
                data["price"],
                data["image_url"],
                data["created_at"],
                data["city"],
                rooms,
                data["content_hash"],
                data.get("latitude"),
                data.get("longitude"),
            ),
        )
        inserted = cursor.rowcount == 1
        reality_id = cursor.lastrowid if inserted else None

        if inserted and reality_id and data.get("photos"):
            for photo in data["photos"]:
                try:
                    cursor.execute(
                        """
                        INSERT IGNORE INTO reality_photos
                            (reality_id, position, photo_url, local_path)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (reality_id, photo["position"], photo["url"], photo["local_path"]),
                    )
                except Exception as e:
                    log.warning("Не удалось сохранить фото для reality_id=%s: %s", reality_id, e)

    conn.commit()
    return "inserted" if inserted else "skipped"


def save_listings(listings: list, db_config: dict) -> dict:
    stats = {"inserted": 0, "skipped": 0, "errors": 0}
    if not listings:
        return stats

    conn = pymysql.connect(**db_config)
    try:
        for ad in listings:
            try:
                result = save_listing(conn, ad)
                stats[result] += 1
            except Exception as e:
                log.error("DB ERROR (slug=%s / ad_id=%s): %s", ad.get("slug"), ad.get("ad_id"), e)
                stats["errors"] += 1
                conn.rollback()
    finally:
        conn.close()
    return stats


# ---------------------------------------------------------------------------
# Парсинг списка (без изменений, кроме передачи session в детальный парсинг)
# ---------------------------------------------------------------------------

def get_photo(container) -> str:
    for img in container.find_all("img"):
        classes = img.get("class") or []
        if "js-lazy" in classes and "img-fluid" in classes:
            src = img.get("data-lazy-src") or img.get("src") or ""
            if src.startswith("http"):
                return src
    for img in container.find_all("img"):
        src = img.get("data-lazy-src") or img.get("src") or ""
        if src.startswith("http"):
            return src
    return ""


def get_price(body):
    price_p = body.find("p", class_="offer-price")
    if not price_p:
        return None
    price_text = price_p.get_text(" ", strip=True)
    m = re.search(r'([\d\s,.]+)\s*€', price_text)
    if not m:
        return None
    value = m.group(1)
    value = value.replace(" ", "").replace(",", "").replace("'", "")
    try:
        return int(value)
    except ValueError:
        return None


def parse_card(h2, city: str):
    a = h2.find_parent("a", href=True) or h2.parent
    if a is None or not a.has_attr("href"):
        return None

    href = a["href"]
    if href.startswith("/"):
        href = BASE + href

    slug = href.rstrip("/").split("/")[-1]
    if not slug:
        return None

    ad_id = extract_ad_id(slug)
    title = h2.get_text(strip=True)

    body = h2.find_parent("div", class_="offer-body")
    if body is None:
        return None

    row = body.parent or body
    photo = get_photo(row)
    price = get_price(body)

    location_a = body.find("a", class_="offer-location")
    location = location_a.get_text(strip=True) if location_a else ""

    params_p = body.find("p", class_="offer-params")
    params = " ".join(params_p.stripped_strings) if params_p else ""

    desc_p = body.find("p", class_="offer-desc")
    description = desc_p.get_text(" ", strip=True) if desc_p else ""

    text = build_text(title, description)
    content_hash = make_content_hash(text, price, city)

    return {
        "slug": slug,
        "ad_id": ad_id,
        "source_url": href,
        "image_url": photo,
        "text": text,
        "price": price,
        "city": city,
        "created_at": datetime.now(),
        "content_hash": content_hash,
        "title": title,
        "location": location,
        "params": params,
        # заполняются позже, в enrich_with_details() -- "full_description"
        # уходит в колонку text_sk при сохранении (см. save_listing)
        "full_description": "",
        "latitude": None,
        "longitude": None,
        "photos": [],
    }


def parse_page(html: str, city: str, seen_hashes: set):
    soup = BeautifulSoup(html, "lxml")
    listings = []

    for h2 in soup.find_all("h2", class_="offer-title"):
        try:
            ad = parse_card(h2, city)
        except Exception as e:
            log.warning("Не удалось распарсить карточку: %s", e)
            continue

        if ad is None:
            continue
        if ad["content_hash"] in seen_hashes:
            continue

        seen_hashes.add(ad["content_hash"])
        listings.append(ad)

    return listings


def get_total_pages(html: str) -> int:
    soup = BeautifulSoup(html, "lxml")
    pagination = (
        soup.find("nav", class_="pagination")
        or soup.find("ul", class_="pagination")
        or soup.find(class_=re.compile("pagination"))
    )
    search_scope = pagination if pagination is not None else soup

    pages = [1]
    for a in search_scope.find_all("a", href=True):
        m = re.search(r"[?&]page=(\d+)", a["href"])
        if m:
            pages.append(int(m.group(1)))
    return max(pages)


def existing_hashes(db_config: dict, hashes: list) -> set:
    """
    Проверяет, какие content_hash уже есть в БД -- чтобы НЕ ходить на
    страницу объявления повторно для уже сохранённых объявлений (это
    самая дорогая операция: лишний HTTP-запрос + скачивание 5 фото).
    """
    if not hashes or not db_config:
        return set()

    conn = pymysql.connect(**db_config)
    try:
        # Явно берём обычный (не Dict-) курсор -- не зависим от того,
        # какой cursorclass задан глобально в DB_CONFIG (там может быть
        # DictCursor, и тогда fetchall() вернёт список dict-ов вместо
        # кортежей, и row[0] упадёт с KeyError, как и произошло).
        with conn.cursor(pymysql.cursors.Cursor) as cur:
            placeholders = ",".join(["%s"] * len(hashes))
            cur.execute(
                f"SELECT content_hash FROM reality WHERE content_hash IN ({placeholders})",
                hashes,
            )
            return {row[0] for row in cur.fetchall()}
    finally:
        conn.close()


def enrich_with_details(listings: list, session: requests.Session, delay: float,
                         db_config: dict, fetch_details: bool):
    """
    Для объявлений, которых ещё нет в БД (по content_hash), заходит на
    страницу объявления и дополняет full_description/latitude/longitude/photos.
    Уже сохранённые объявления не трогаем -- незачем повторно тянуть фото.
    """
    if not fetch_details or not listings:
        return listings

    hashes = [ad["content_hash"] for ad in listings]
    already_in_db = existing_hashes(db_config, hashes) if db_config else set()

    for ad in listings:
        if ad["content_hash"] in already_in_db:
            continue
        time.sleep(delay)
        detail = fetch_detail(ad["source_url"], ad["ad_id"], session)
        ad["full_description"] = detail["full_description"]
        ad["latitude"] = detail["latitude"]
        ad["longitude"] = detail["longitude"]
        ad["photos"] = detail["photos"]

    return listings


def fetch_city(city: str, max_pages: int, session: requests.Session, delay: float):
    all_listings = []
    seen_hashes = set()
    url = f"{BASE}/byty/{city}/prenajom/"

    resp = session.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    html = resp.text

    total_pages = get_total_pages(html)
    pages_to_fetch = min(total_pages, max_pages) if max_pages else total_pages

    all_listings.extend(parse_page(html, city, seen_hashes))

    for page in range(2, pages_to_fetch + 1):
        time.sleep(delay)
        page_url = f"{url}?page={page}"
        try:
            r = session.get(page_url, headers=HEADERS, timeout=20)
        except requests.RequestException as e:
            log.warning("Ошибка запроса страницы %s (%s): %s", page, city, e)
            break
        if r.status_code != 200:
            log.warning("Страница %s (%s) вернула статус %s, останавливаемся", page, city, r.status_code)
            break
        all_listings.extend(parse_page(r.text, city, seen_hashes))

    return all_listings


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Парсер аренды квартир reality.sk")
    parser.add_argument("--cities", nargs="+", default=CITY)
    parser.add_argument("--pages", type=int, default=1)
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--no-db", action="store_true")
    parser.add_argument("--no-details", action="store_true",
                         help="не заходить на карточку объявления (старое поведение, быстрее)")
    parser.add_argument("--migrate", action="store_true",
                         help="применить ALTER TABLE / CREATE TABLE из MIGRATION_SQL и продолжить")
    args = parser.parse_args()

    db_config = None if args.no_db else _get_db_config()

    if args.migrate and db_config:
        run_migration(db_config)

    session = requests.Session()
    total_stats = {"inserted": 0, "skipped": 0, "errors": 0}

    for city in args.cities:
        log.info("=" * 80)
        log.info("ГОРОД: %s", city)
        log.info("=" * 80)
        try:
            listings = fetch_city(city, args.pages, session, args.delay)
        except requests.RequestException as e:
            log.error("Ошибка запроса для %s: %s", city, e)
            time.sleep(args.delay)
            continue

        if not listings:
            log.info("Объявления не найдены.")
            time.sleep(args.delay)
            continue

        listings = enrich_with_details(
            listings, session, args.delay, db_config,
            fetch_details=not args.no_details,
        )

        if not args.no_db:
            stats = save_listings(listings, db_config)
            log.info(
                "БД: новых=%d пропущено(уже есть)=%d ошибок=%d",
                stats["inserted"], stats["skipped"], stats["errors"],
            )
            for k in total_stats:
                total_stats[k] += stats[k]
        else:
            for ad in listings:
                print(f"slug:        {ad['slug']}")
                print(f"ad_id:       {ad['ad_id']}")
                print(f"Title:       {ad['title']}")
                print(f"URL:         {ad['source_url']}")
                print(f"Price:       {ad['price']}")
                print(f"Full desc:   {(ad['full_description'] or '')[:200]}")
                print(f"Lat/Lon:     {ad['latitude']}, {ad['longitude']}")
                print(f"Photos:      {len(ad['photos'])}")
                print("-" * 80)

        time.sleep(args.delay)

    if not args.no_db:
        log.info("=" * 80)
        log.info(
            "ИТОГО: новых=%d пропущено=%d ошибок=%d",
            total_stats["inserted"], total_stats["skipped"], total_stats["errors"],
        )


if __name__ == "__main__":
    main()