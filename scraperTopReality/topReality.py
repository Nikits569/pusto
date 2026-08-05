#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Парсер объявлений АРЕНДЫ (prenájom) с topreality.sk по ГОРОДАМ (obec) +
сохранение в MySQL.

=== ИЗМЕНЕНИЕ ОТНОСИТЕЛЬНО ПРЕДЫДУЩЕЙ ВЕРСИИ ===

    Раньше выборка строилась по КРАЯМ (regions) через параметры поиска
    obec=c700-Prešovský kraj / region[0]=700 + список type[] с кодами всех
    подтипов "Byty". Теперь выборка строится НЕПОСРЕДСТВЕННО ПО ГОРОДАМ
    через "чистые" SEO-урлы вида:

        https://www.topreality.sk/<city-slug>/byty/prenajom.html        -- страница 1
        https://www.topreality.sk/<city-slug>/byty/prenajom2.html       -- страница 2
        https://www.topreality.sk/<city-slug>/byty/prenajom3.html       -- страница 3
        ...

    Категория "byty" в самом урле уже ограничивает выборку одними только
    квартирами (все подтипы: garsónka, 1-5 izbový, mezonet, apartmán,
    loft и т.д.) -- отдельный список APARTMENT_TYPE_IDS и параметры
    type[]/region[]/obec больше не нужны.

    slug города -- это то же самое, что раньше было "region_key" (те же
    8 ключей: bratislava, trnava, trencin, nitra, zilina,
    banska-bystrica, presov, kosice), но теперь это ИМЕННО ГОРОД
    (областной/районный центр), а не весь край целиком.

    Дополнительно на всякий случай (страховка от того, что фильтр
    "prenajom" в урле почему-то отдаст и объявления о продаже) каждая
    карточка проверяется по тексту цены: если это явно "продажная" цена
    (нет признаков аренды -- "mesiac"/"dohodou"/пусто, и т.п.) -- такая
    карточка отбрасывается, см. is_rental_price().

=== Остальная логика идентична предыдущей версии (по краям) ===

Для КАЖДОГО НОВОГО (ещё не сохранённого в БД по content_hash) объявления
скрипт дополнительно заходит на страницу самого объявления и вытаскивает:

    1. ПОЛНОЕ описание (не обрезанный сниппет со страницы списка) --
       сохраняется в колонку text_sk.
    2. Первые 5 фото объявления -- СКАЧИВАЕТ ФАЙЛЫ НА ДИСК в
       PHOTOS_DIR/<ad_id>/1.jpg .. 5.jpg. Отдельной таблицы фото в БД
       нет -- только файлы на диске.
    3. Координаты (latitude/longitude), если сайт их отдаёт в HTML.

Уже сохранённые объявления повторно на карточку НЕ заходят (проверка по
content_hash).

Итоговые колонки topreality (после миграции, см. migration.sql):
    topreality_id, ad_id, source_url, text, price, image_url, created_at,
    city, latitude, longitude, text_en, text_sk, rooms, content_hash

Запуск:
    python3 topreality_sk_parser.py --no-db                # только проверка вывода
    python3 topreality_sk_parser.py                         # с записью в БД
    python3 topreality_sk_parser.py --cities presov kosice --pages 2
    python3 topreality_sk_parser.py --no-details             # без захода на карточки
    python3 topreality_sk_parser.py --migrate --no-db        # только применить ALTER и выйти

Через cron:
    */15 * * * * cd /var/www/app/pusto/scraperTopReality && \
        flock -n /tmp/topreality_parser.lock \
        /var/www/app/pusto/pusto/venv/bin/python3 -u topreality_sk_parser.py \
        >> /var/log/topreality.log 2>&1

ВАЖНО про переменные окружения:
    export PHOTOS_DIR="photos"   # опционально, по умолчанию ./photos
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
from urllib.parse import urljoin

import requests
import pymysql
from bs4 import BeautifulSoup
from config import DB_CONFIG

# ---------------------------------------------------------------------------
# Логирование
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("topreality_sk_parser")


# ---------------------------------------------------------------------------
# Константы
# ---------------------------------------------------------------------------

BASE = "https://www.topreality.sk"

# Города для парсинга. Ключ -- slug (используется в урле), значение --
# человекочитаемое название (для логов/отчётов). Это те же 8 ключей, что
# раньше были "региональными" -- теперь это конкретные города.
CITIES = {
    "bratislava": "Bratislava",
    "trnava": "Trnava",
    "trencin": "Trenčín",
    "nitra": "Nitra",
    "zilina": "Žilina",
    "banska-bystrica": "Banská Bystrica",
    "presov": "Prešov",
    "kosice": "Košice",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "sk-SK,sk;q=0.9,en;q=0.8",
}

LISTING_LINK_RE = re.compile(r"-r(\d+)\.html")

ROOM_PATTERNS = [
    (r'\bgars[oó]nka\b', 1),
    (r'\bgarzonka\b', 1),
    (r'\bštúdio\b', 1),
    (r'\bstudio\b', 1),
    (r'\b([1-9])\s*[- ]?\s*izbov[ýyiáé]*', None),
    (r'\b([1-9])\s*izb\b', None),
    (r'\b([1-9])\+kk\b', None),
    (r'\b([1-9])\+1\b', None),
]

# Сколько фото скачивать с карточки объявления
MAX_PHOTOS = 5

# Куда складывать скачанные фото на диске: photos/<ad_id>/1.jpg ...
PHOTOS_DIR = os.getenv("PHOTOS_DIR", "photos")

# Регексы для поиска координат в сыром HTML/JSON, если по тегам не нашли
GEO_JSON_RE = re.compile(
    r'"lat(?:itude)?"\s*:\s*"?(-?\d{1,3}\.\d+)"?\s*,\s*"lon(?:g|gitude)?"\s*:\s*"?(-?\d{1,3}\.\d+)"?',
    re.IGNORECASE,
)
ICBM_RE = re.compile(r'([\-0-9.]+),\s*([\-0-9.]+)')

MIGRATION_SQL = [
    "ALTER TABLE topreality ADD COLUMN IF NOT EXISTS latitude DOUBLE(10,7) NULL AFTER city",
    "ALTER TABLE topreality ADD COLUMN IF NOT EXISTS longitude DOUBLE(10,7) NULL AFTER latitude",
]


def _get_db_config() -> dict:
    if not DB_CONFIG:
        log.error("DB_CONFIG не задан в config.py")
        sys.exit(1)
    return DB_CONFIG


def run_migration(db_config: dict):
    """Накатывает ALTER из MIGRATION_SQL. Безопасно запускать повторно."""
    conn = pymysql.connect(**db_config)
    try:
        with conn.cursor() as cur:
            for stmt in MIGRATION_SQL:
                try:
                    cur.execute(stmt)
                except Exception as e:
                    if "Duplicate column" in str(e) or "already exists" in str(e):
                        log.info("Уже применено: %s", stmt.strip().splitlines()[0])
                    else:
                        raise
        conn.commit()
        log.info("Миграция схемы применена.")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Утилиты
# ---------------------------------------------------------------------------

def extract_rooms(*texts: str):
    source = " ".join(t or "" for t in texts).lower()
    for pattern, fixed in ROOM_PATTERNS:
        m = re.search(pattern, source)
        if m:
            return fixed if fixed is not None else int(m.group(1))
    return None


def make_content_hash(text: str, price, city: str) -> str:
    normalized_text = re.sub(r"\s+", " ", (text or "").strip().lower())
    raw = f"{normalized_text}|{price}|{(city or '').strip().lower()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_search_url(city_slug: str, page: int) -> str:
    """
    Страница 1:  https://www.topreality.sk/<city>/byty/prenajom.html
    Страница N:  https://www.topreality.sk/<city>/byty/prenajomN.html
    (N=2,3,4,... -- без знака "-" перед числом, в отличие от общего
    поиска vyhladavanie-nehnutelnosti-N.html)
    """
    if page <= 1:
        return f"{BASE}/{city_slug}/byty/prenajom.html"
    return f"{BASE}/{city_slug}/byty/prenajom{page}.html"


def is_rental_price(price_text: str) -> bool:
    """
    Строгая страховочная проверка: пропускаем карточку ТОЛЬКО если в её
    цене явно есть признак аренды -- "mesiac"/"mesačne" (на сайте цена
    аренды всегда отображается как "580,00 €/mesiac", см. скриншот
    объявления). Это единственный надёжный признак -- слово "dohodou"
    (цена по договорённости) встречается и у объявлений о ПРОДАЖЕ, а
    отсутствие суффикса "/m2" НЕ гарантирует аренду (у карточек продажи
    цена за м2 нередко лежит в отдельном соседнем элементе, а не в том
    же price_text, поэтому старая версия проверки иногда пропускала
    продажу как аренду).

    По умолчанию -- ОТБРАСЫВАЕМ (False), если "mesiac" не найден, даже
    если price_text пустой или "dohodou". Строже, зато гарантированно не
    пропустит ни одной продажи.
    """
    if not price_text:
        return False
    low = price_text.lower().replace(" ", "")
    return "mesiac" in low or "mesacne" in low.replace("č", "c")


# ---------------------------------------------------------------------------
# NEW: парсинг страницы конкретного объявления (описание / гео / фото)
# ---------------------------------------------------------------------------

def extract_full_description(soup: BeautifulSoup) -> str:
    """
    Полное описание на странице объявления. Пробуем по убыванию надёжности:

    1. schema.org itemprop="description" (частый паттерн для SEO).
    2. Типичные для этой сети сайтов (unitedclassifieds: topreality.sk /
       reality.sk / nehnutelnosti.sk) классы контейнера описания.
    3. Эвристика: ищем текст рядом со ссылкой "Zobraziť celý popis" и
       берём его родительский блок, обрезая по стоп-словам ("Podobné
       inzeráty" и т.п.), чтобы не утащить в описание блок похожих
       объявлений.

    Если ничего не нашлось -- возвращает "" (пустую строку, НЕ None),
    это осознанно: чтобы строка не попадала повторно в выборку backfill
    как "необработанная" (см. WHERE text_sk IS NULL).
    """
    node = soup.find(attrs={"itemprop": "description"})
    if node:
        txt = node.get_text("\n", strip=True)
        if txt and len(txt) > 20:
            return txt

    for cls_re in (
        r"description[-_]?text", r"detail[-_]?description",
        r"estate[-_]?description", r"popis[-_]?text",
        r"\bpopis\b", r"\bdescription\b",
    ):
        node = soup.find(["div", "p", "section"], class_=re.compile(cls_re, re.I))
        if node:
            txt = node.get_text("\n", strip=True)
            if txt and len(txt) > 20:
                return txt

    stop_words = ("zobraziť celý popis", "podobné inzeráty", "kontakt na predajcu")
    candidate = soup.find(string=re.compile(r"cel[ýy]\s+popis", re.I))
    if candidate:
        container = candidate.find_parent(["div", "section"])
        for _ in range(2):
            if container and container.parent:
                if len(container.parent.get_text(strip=True)) > len(container.get_text(strip=True)):
                    container = container.parent
        if container:
            full_text = container.get_text("\n", strip=True)
            lower = full_text.lower()
            cut_at = len(full_text)
            for marker in stop_words:
                idx = lower.find(marker)
                if idx != -1:
                    cut_at = min(cut_at, idx)
            desc = full_text[:cut_at].strip()
            if len(desc) > 20:
                return desc

    return ""


def extract_geo(soup: BeautifulSoup, html: str):
    """
    Пытается достать (latitude, longitude) несколькими способами, от
    самого надёжного к самому "на всякий случай":

    1. JSON-LD (schema.org geo / latitude / longitude).
    2. Meta-теги geo.position / ICBM.
    3. Произвольный JSON в <script> с ключами lat/lng.

    Если ничего не найдено -- (None, None).
    """
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except (ValueError, TypeError):
            continue
        candidates = data if isinstance(data, list) else [data]
        for item in candidates:
            geo = item.get("geo") if isinstance(item, dict) else None
            if isinstance(geo, dict):
                lat, lon = geo.get("latitude"), geo.get("longitude")
                if lat is not None and lon is not None:
                    try:
                        return float(lat), float(lon)
                    except ValueError:
                        pass

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

    m = GEO_JSON_RE.search(html)
    if m:
        try:
            return float(m.group(1)), float(m.group(2))
        except ValueError:
            pass

    return None, None


def _gallery_url(source_url: str) -> str:
    """https://www.topreality.sk/<slug>-r<id>.html -> .../<slug>-r<id>/galeria.html"""
    if source_url.endswith(".html"):
        return source_url[: -len(".html")] + "/galeria.html"
    return source_url.rstrip("/") + "/galeria.html"


def extract_gallery_photos(session: requests.Session, source_url: str, ad_id: str, limit: int = MAX_PHOTOS):
    """
    topreality.sk отдаёт полноразмерные фото прямыми ссылками на отдельной
    странице .../galeria.html: <a href="/topfoto/<slug>-dN-XXX-<ad_id>_n.jpg">.
    Ссылки на превью лежат в /topfoto/t/... -- их отбрасываем.
    """
    gallery_url = _gallery_url(source_url)
    try:
        resp = session.get(gallery_url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as e:
        log.warning("Не удалось загрузить галерею %s: %s", gallery_url, e)
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    urls = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/topfoto/" not in href or "/topfoto/t/" in href:
            continue
        if not href.lower().split("?")[0].endswith((".jpg", ".jpeg", ".png", ".webp")):
            continue
        full_url = urljoin(BASE, href)
        if full_url not in urls:
            urls.append(full_url)
        if len(urls) >= limit:
            break
    return urls


def download_photos(photo_urls, ad_id: str, session: requests.Session):
    """
    Скачивает фото на диск в PHOTOS_DIR/<ad_id>/1.jpg, 2.jpg, ...
    Никакой записи в БД -- только файлы на диске.
    """
    result = []
    folder = os.path.join(PHOTOS_DIR, str(ad_id))
    os.makedirs(folder, exist_ok=True)

    for i, url in enumerate(photo_urls, start=1):
        ext = os.path.splitext(url.split("?")[0])[1] or ".jpg"
        local_path = os.path.join(folder, f"{i}{ext}")
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
    Заходит на страницу объявления, возвращает
    {"full_description": str, "latitude": float|None, "longitude": float|None,
     "photos": [{"url", "local_path", "position"}, ...]}
    "full_description" -- ключ внутреннего словаря Python; при сохранении
    в БД (save_listing) его значение кладётся в колонку text_sk.
    Никогда не бросает исключение наружу.
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
    adress = extract_location(soup)
    photo_urls = extract_gallery_photos(session, url, ad_id, MAX_PHOTOS)

    full_description = extract_full_description(soup)
    latitude, longitude = extract_geo(soup, resp.text)
    photo_urls = extract_gallery_photos(session, url, ad_id, MAX_PHOTOS)
    photos = download_photos(photo_urls, ad_id, session) if (download and photo_urls) else (
        [{"url": u, "local_path": None, "position": i} for i, u in enumerate(photo_urls, 1)]
    )

    return {
        "full_description": full_description,
        "latitude": latitude,
        "longitude": longitude,
        "adress": adress,
        "photos": photos,
    }


# ---------------------------------------------------------------------------
# БД
# ---------------------------------------------------------------------------

def save_listing(conn, data: dict) -> str:
    rooms = extract_rooms(data.get("title", ""), data.get("room_type_text", ""))
    with conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT IGNORE INTO topreality
                (ad_id, source_url, text_sk, price, image_url,
                 created_at, city, text_en, text, rooms, content_hash,
                 latitude, longitude, adress)
            VALUES
                (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                data["topreality_id"],
                data["source_url"],
                data.get("full_description") or None,
                data["price"],
                data["image_url"],
                data["created_at"],
                data["city"],
                None,
                data["text"],
                rooms,
                data["content_hash"],
                data.get("latitude"),
                data.get("longitude"),
                data.get("adress"),
            ),
        )
        inserted = cursor.rowcount == 1
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
                log.error("DB ERROR (%s): %s", ad.get("topreality_id"), e)
                stats["errors"] += 1
                conn.rollback()
    finally:
        conn.close()
    return stats


def existing_hashes(db_config: dict, hashes: list) -> set:
    """
    Какие content_hash уже есть в БД -- чтобы НЕ заходить на карточку
    повторно для уже сохранённых объявлений.
    """
    if not hashes or not db_config:
        return set()

    conn = pymysql.connect(**db_config)
    try:
        with conn.cursor(pymysql.cursors.Cursor) as cur:
            placeholders = ",".join(["%s"] * len(hashes))
            cur.execute(
                f"SELECT content_hash FROM topreality WHERE content_hash IN ({placeholders})",
                hashes,
            )
            return {row[0] for row in cur.fetchall()}
    finally:
        conn.close()


def enrich_with_details(listings: list, session: requests.Session, delay: float,
                         db_config: dict, fetch_details: bool):
    """
    Для объявлений, которых ещё нет в БД (по content_hash), заходит на
    страницу объявления и дополняет full_description/latitude/longitude,
    скачивает фото на диск. Уже сохранённые объявления не трогаем.
    """
    if not fetch_details or not listings:
        return listings

    hashes = [ad["content_hash"] for ad in listings]
    already_in_db = existing_hashes(db_config, hashes) if db_config else set()

    for ad in listings:
        if ad["content_hash"] in already_in_db:
            continue
        time.sleep(delay)
        detail = fetch_detail(ad["source_url"], ad["topreality_id"], session)

        ad["full_description"] = detail["full_description"]
        ad["latitude"] = detail["latitude"]
        ad["longitude"] = detail["longitude"]
        ad["adress"] = detail["adress"]
        ad["photos"] = detail["photos"]

    return listings


# ---------------------------------------------------------------------------
# Парсинг карточки списка (без завязки на конкретные CSS-классы)
# ---------------------------------------------------------------------------

def find_card(h2):
    return h2.find_parent("div", class_=re.compile(r"\bcard-info-left\b"))


def parse_price(price_text: str):
    if not price_text or "dohodou" in price_text.lower():
        return None, None

    before_eur = price_text.split("€")[0]
    numbers = re.findall(r'\d[\d\s]*(?:,\d{2})?', before_eur)
    if not numbers:
        return None, None

    def to_int(num_str: str):
        whole = num_str.replace(" ", "").split(",")[0]
        return int(whole) if whole.isdigit() else None

    price = to_int(numbers[0])
    fee = to_int(numbers[1]) if len(numbers) > 1 else None
    return price, fee


def extract_location(soup: BeautifulSoup):
    for li in soup.select("li.list-group-item"):
        span = li.find("span")

        if not span:
            continue

        if span.get_text(strip=True).lower() == "ulica":
            strong = li.find("strong")
            if strong:
                return strong.get_text(" ", strip=True)

    return None

def extract_image(soup, topreality_id: str, href: str):
    id_re = re.compile(re.escape(topreality_id) + r"\.html")
    for a in soup.find_all("a", href=id_re):
        img = a.find("img")
        if img is None:
            continue
        classes = img.get("class") or []
        if "rkLogo" in classes:
            continue
        src = (
            img.get("data-src") or img.get("data-lazy-src")
            or img.get("data-original") or img.get("src") or ""
        )
        if not src:
            continue
        if "logo" in src.lower() or "topreality-blank" in src:
            continue
        if src.startswith("//"):
            return "https:" + src
        if src.startswith("http"):
            return src
        if src.startswith("/"):
            return BASE + src
    return None


def parse_card(h2, city: str, soup):
    link = h2.find("a", href=LISTING_LINK_RE)
    if link is None:
        return None

    href = link.get("href", "")
    if href.startswith("/"):
        href = BASE + href
    elif not href.startswith("http"):
        return None

    m = LISTING_LINK_RE.search(href)
    if not m:
        return None
    topreality_id = m.group(1)

    title = h2.get_text(strip=True)

    card = find_card(h2)
    if card is None:
        return None

    price_el = card.select_one("div.prices strong.price")
    price_text = price_el.get_text(" ", strip=True) if price_el else ""

    # Страховка: пропускаем карточку, если по тексту цены похоже, что
    # это объявление о ПРОДАЖЕ, а не об аренде (см. is_rental_price).
    if not is_rental_price(price_text):
        return None

    price, energy_fee = parse_price(price_text)

    addr_el = card.select_one("span.location-address")
    city_el = card.select_one("span.location-city")
    location_parts = [
        addr_el.get_text(strip=True) if addr_el else "",
        city_el.get_text(strip=True) if city_el else "",
    ]
    location = ", ".join(p for p in location_parts if p)

    area = None
    area_el = card.select_one("span.areas span.value")
    if area_el:
        area_m = re.search(r'(\d+)', area_el.get_text(" ", strip=True))
        if area_m:
            area = int(area_m.group(1))

    room_type_text = ""
    links_ul = card.find_parent("div", class_=re.compile(r"\bcard\b")) or card
    room_link = links_ul.select_one("div.links li a")
    if room_link:
        room_type_text = room_link.get_text(strip=True)

    image_url = extract_image(soup, topreality_id, href)

    text = title
    if location:
        text += f" — {location}"
    if energy_fee:
        text += f" (+{energy_fee} € energie)"

    content_hash = make_content_hash(text, price, city)

    return {
        "topreality_id": topreality_id,
        "source_url": href,
        "title": title,
        "text": text,
        "price": price,
        "energy_fee": energy_fee,
        "area": area,
        "location": location,
        "room_type_text": room_type_text,
        "image_url": image_url,
        "city": city,
        "created_at": datetime.now(),
        "content_hash": content_hash,
        # заполняются позже, в enrich_with_details() -- "full_description"
        # уходит в колонку text_sk при сохранении (см. save_listing)
        "full_description": "",
        "latitude": None,
        "longitude": None,
        "photos": [],
        "adress": None,

    }


def parse_page(html: str, city: str, seen_hashes: set):
    soup = BeautifulSoup(html, "lxml")
    listings = []
    headers_found = soup.select("h2.card-title") or soup.find_all("h2")
    for h2 in headers_found:
        try:
            ad = parse_card(h2, city, soup)
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


def get_total_pages(html: str, city_slug: str) -> int:
    """
    Ищет ссылки вида /<city_slug>/byty/prenajomN.html и возвращает
    максимальный номер страницы N (страница 1 = .../prenajom.html, без
    номера, поэтому 1 всегда в списке "по умолчанию").
    """
    soup = BeautifulSoup(html, "lxml")
    page_re = re.compile(re.escape(city_slug) + r"/byty/prenajom(\d+)\.html")
    pages = [1]
    for a in soup.find_all("a", href=True):
        m = page_re.search(a["href"])
        if m:
            n = int(m.group(1))
            if 0 < n < 500:
                pages.append(n)
    return max(pages)


def fetch_city(city_slug: str, max_pages: int, session: requests.Session, delay: float):
    if city_slug not in CITIES:
        log.warning("Неизвестный город: %s (пропускаю)", city_slug)
        return []

    all_listings = []
    seen_hashes = set()

    first_url = build_search_url(city_slug, page=1)
    resp = session.get(first_url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    html = resp.text

    total_pages = get_total_pages(html, city_slug)
    pages_to_fetch = min(total_pages, max_pages) if max_pages else total_pages

    all_listings.extend(parse_page(html, city_slug, seen_hashes))

    for page in range(2, pages_to_fetch + 1):
        time.sleep(delay)
        page_url = build_search_url(city_slug, page)
        try:
            r = session.get(page_url, headers=HEADERS, timeout=20)
        except requests.RequestException as e:
            log.warning("Ошибка запроса страницы %s (%s): %s", page, city_slug, e)
            break

        if r.status_code != 200:
            log.warning("Страница %s (%s) вернула статус %s, останавливаемся",
                        page, city_slug, r.status_code)
            break

        all_listings.extend(parse_page(r.text, city_slug, seen_hashes))

    return all_listings


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Парсер аренды topreality.sk по городам")
    parser.add_argument("--cities", nargs="+", default=list(CITIES.keys()),
                         help=f"Slug'и городов из списка: {', '.join(CITIES.keys())}")
    parser.add_argument("--pages", type=int, default=1)
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--no-db", action="store_true")
    parser.add_argument("--no-details", action="store_true",
                         help="не заходить на карточку объявления (старое поведение, быстрее)")
    parser.add_argument("--migrate", action="store_true",
                         help="применить ALTER TABLE из MIGRATION_SQL и продолжить")
    args = parser.parse_args()

    db_config = None if args.no_db else _get_db_config()

    if args.migrate and db_config:
        run_migration(db_config)

    session = requests.Session()
    total_stats = {"inserted": 0, "skipped": 0, "errors": 0}

    for city in args.cities:
        log.info("=" * 80)
        log.info("ГОРОД: %s (%s)", city, CITIES.get(city, "?"))
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
                print(f"ID:          {ad['topreality_id']}")
                print(f"Title:       {ad['title']}")
                print(f"URL:         {ad['source_url']}")
                print(f"Location:    {ad['location']}")
                print(f"Price:       {ad['price']}  (+ energie: {ad['energy_fee']})")
                print(f"Lat/Lon:     {ad['latitude']}, {ad['longitude']}")
                print(f"Photos:      {len(ad['photos'])}")
                print(f"Hash:        {ad['content_hash']}")
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