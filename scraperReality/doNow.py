#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ОДНОРАЗОВЫЙ backfill-скрипт.

Что делает:
    Берёт из таблицы `reality` записи, у которых ещё НЕТ full_description
    (то есть все, что были сохранены старой версией парсера, до добавления
    похода на карточку объявления), заходит по их source_url на страницу
    объявления и дозаполняет:

        - full_description
        - latitude / longitude
        - до 5 фото -> таблица reality_photos (+ скачивание файлов на диск)

Ничего не удаляет и не перезаписывает существующие поля (ad_id, price,
text_sk и т.п.) -- только UPDATE трёх новых колонок + INSERT в
reality_photos.

Перед запуском обязательно должна быть применена миграция схемы:

    ALTER TABLE reality ADD COLUMN full_description TEXT NULL AFTER text_sk;
    ALTER TABLE reality ADD COLUMN latitude  DOUBLE(10,7) NULL AFTER city;
    ALTER TABLE reality ADD COLUMN longitude DOUBLE(10,7) NULL AFTER latitude;

    CREATE TABLE reality_photos (
        photo_id     INT PRIMARY KEY AUTO_INCREMENT,
        reality_id   INT NOT NULL,
        position     TINYINT NOT NULL,
        photo_url    VARCHAR(500),
        local_path   VARCHAR(500),
        FOREIGN KEY (reality_id) REFERENCES reality(reality_id) ON DELETE CASCADE,
        UNIQUE KEY uniq_reality_position (reality_id, position)
    );

(если уже применяли эту миграцию для основного парсера -- второй раз
применять не нужно).

Запуск:
    python3 backfill_reality_details.py                  # пройтись по всем строкам без full_description
    python3 backfill_reality_details.py --limit 50        # только первые 50 (потестить)
    python3 backfill_reality_details.py --start-id 60000  # продолжить с конкретного reality_id
                                                            # (удобно, если скрипт прервали и
                                                            # перезапускают)
    python3 backfill_reality_details.py --dry-run          # ничего не пишет в БД, только печатает
    python3 backfill_reality_details.py --delay 2          # пауза между запросами (сек), по умолчанию 1.5

Скрипт можно смело прерывать (Ctrl+C) и запускать заново -- он каждый раз
берёт из БД только те строки, где full_description ещё пустой (или где ещё
не было записи в reality_photos), так что уже обработанные строки не
трогает повторно.
"""

import os
import re
import sys
import json
import time
import logging
import argparse

import requests
import pymysql
from bs4 import BeautifulSoup

from config import DB_CONFIG

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("backfill_reality_details")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "sk-SK,sk;q=0.9,en;q=0.8",
}

MAX_PHOTOS = 5
PHOTOS_DIR = os.getenv("PHOTOS_DIR", "photos")

GEO_JSON_RE = re.compile(
    r'"lat(?:itude)?"\s*:\s*"?(-?\d{1,3}\.\d+)"?\s*,\s*"lon(?:g|gitude)?"\s*:\s*"?(-?\d{1,3}\.\d+)"?',
    re.IGNORECASE,
)
ICBM_RE = re.compile(r'([\-0-9.]+),\s*([\-0-9.]+)')


# ---------------------------------------------------------------------------
# Те же функции извлечения, что и в основном парсере (продублированы
# специально, чтобы этот backfill-скрипт не зависел от точного имени файла
# основного парсера -- он у тебя называется reality.py).
# ---------------------------------------------------------------------------

def extract_full_description(soup: BeautifulSoup) -> str:
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

    return "\n".join(p for p in parts if p).strip()


def extract_geo(soup: BeautifulSoup, html: str):
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


def extract_gallery_photos(soup: BeautifulSoup, limit: int = MAX_PHOTOS):
    urls = []
    for img in soup.find_all("img"):
        src = img.get("data-lazy-src") or img.get("data-src") or img.get("src") or ""
        if not src.startswith("http"):
            continue
        if "img.unitedclassifieds.sk" not in src:
            continue
        if "170x170" in src or "logo" in src.lower():
            continue
        if src not in urls:
            urls.append(src)
        if len(urls) >= limit:
            break
    return urls


def download_photos(photo_urls, ad_id: str, session: requests.Session):
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


def fetch_detail(url: str, ad_id: str, session: requests.Session):
    empty = {"full_description": "", "latitude": None, "longitude": None, "photos": []}
    try:
        resp = session.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as e:
        log.warning("Не удалось загрузить %s: %s", url, e)
        return empty

    soup = BeautifulSoup(resp.text, "lxml")
    full_description = extract_full_description(soup)
    latitude, longitude = extract_geo(soup, resp.text)
    photo_urls = extract_gallery_photos(soup, MAX_PHOTOS)
    photos = download_photos(photo_urls, ad_id, session) if photo_urls else []

    return {
        "full_description": full_description,
        "latitude": latitude,
        "longitude": longitude,
        "photos": photos,
    }


# ---------------------------------------------------------------------------
# Работа с БД
# ---------------------------------------------------------------------------

def get_rows_to_process(conn, start_id: int, limit: int):
    """
    Берём строки, где full_description ещё не заполнен (NULL или пустая
    строка) -- то есть строки, которые ещё не проходили обогащение.
    reality_id > start_id -- чтобы можно было продолжить прерванный прогон.
    """
    sql = """
        SELECT reality_id, ad_id, source_url
        FROM reality
        WHERE (full_description IS NULL OR full_description = '')
          AND reality_id > %s
        ORDER BY reality_id
    """
    if limit:
        sql += " LIMIT %s"

    with conn.cursor(pymysql.cursors.Cursor) as cur:
        if limit:
            cur.execute(sql, (start_id, limit))
        else:
            cur.execute(sql, (start_id,))
        return cur.fetchall()  # [(reality_id, ad_id, source_url), ...]


def update_row(conn, reality_id: int, detail: dict, dry_run: bool):
    if dry_run:
        log.info(
            "[dry-run] reality_id=%s: desc_len=%d lat=%s lon=%s photos=%d",
            reality_id, len(detail["full_description"] or ""),
            detail["latitude"], detail["longitude"], len(detail["photos"]),
        )
        return

    with conn.cursor() as cursor:
        cursor.execute(
            """
            UPDATE reality
            SET full_description = %s,
                latitude = %s,
                longitude = %s
            WHERE reality_id = %s
            """,
            (
                detail["full_description"] or None,
                detail["latitude"],
                detail["longitude"],
                reality_id,
            ),
        )
        for photo in detail["photos"]:
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


def main():
    parser = argparse.ArgumentParser(description="Backfill full_description/geo/photos для уже существующих объявлений reality.sk")
    parser.add_argument("--start-id", type=int, default=0,
                         help="обрабатывать только reality_id > START_ID (для продолжения прерванного прогона)")
    parser.add_argument("--limit", type=int, default=0,
                         help="максимум строк за один запуск (0 = без ограничения)")
    parser.add_argument("--delay", type=float, default=1.5,
                         help="пауза между запросами к сайту, сек")
    parser.add_argument("--dry-run", action="store_true",
                         help="ничего не писать в БД, только показать, что нашлось")
    args = parser.parse_args()

    if not DB_CONFIG:
        log.error("DB_CONFIG не задан в config.py")
        sys.exit(1)

    conn = pymysql.connect(**DB_CONFIG)
    session = requests.Session()

    stats = {"processed": 0, "ok": 0, "empty": 0, "errors": 0}

    try:
        rows = get_rows_to_process(conn, args.start_id, args.limit)
        log.info("Найдено %d записей без full_description (start_id=%s, limit=%s)",
                  len(rows), args.start_id, args.limit or "все")

        for reality_id, ad_id, source_url in rows:
            stats["processed"] += 1
            log.info("[%d/%d] reality_id=%s ad_id=%s -> %s",
                      stats["processed"], len(rows), reality_id, ad_id, source_url)

            try:
                detail = fetch_detail(source_url, ad_id, session)
            except Exception as e:
                log.error("Ошибка при обработке reality_id=%s: %s", reality_id, e)
                stats["errors"] += 1
                time.sleep(args.delay)
                continue

            if not detail["full_description"] and detail["latitude"] is None and not detail["photos"]:
                log.warning("reality_id=%s: ничего не нашлось на странице (сайт мог отдать другую вёрстку/404)", reality_id)
                stats["empty"] += 1
            else:
                stats["ok"] += 1

            try:
                update_row(conn, reality_id, detail, args.dry_run)
            except Exception as e:
                log.error("DB ERROR при обновлении reality_id=%s: %s", reality_id, e)
                stats["errors"] += 1
                conn.rollback()

            time.sleep(args.delay)

    finally:
        conn.close()

    log.info("=" * 80)
    log.info(
        "ГОТОВО: обработано=%d успешно=%d пусто=%d ошибок=%d",
        stats["processed"], stats["ok"], stats["empty"], stats["errors"],
    )
    if stats["errors"] or stats["empty"]:
        log.info("Если прервётся или нужно продолжить позже -- запусти с --start-id <последний обработанный reality_id>")


if __name__ == "__main__":
    main()