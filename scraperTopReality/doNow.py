#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
topreality_backfill.py
========================
ОДНОРАЗОВЫЙ скрипт для дозаполнения уже существующих строк в таблице
topreality, у которых ещё нет full_description (сохранены старой версией
парсера, до появления захода на карточку).

Для каждой такой строки:
    - заходит на её source_url (переиспользует fetch_detail из
      topreality_sk_parser.py -- та же логика извлечения, что и в новых
      объявлениях)
    - забирает full_description, latitude, longitude
    - скачивает до 5 фото на диск в PHOTOS_DIR/<ad_id>/ (без отдельной
      таблицы в БД, как и в основном парсере)
    - обновляет ТОЛЬКО эти 3 текстовых поля, остальные данные строки не трогает

Если full_description на странице не нашлось, пишем '' (пустую строку),
а не NULL -- чтобы строка не попадала в выборку backfill повторно и
бесконечно (страница реально была обработана, просто там нечего было
взять).

Безопасное прерывание/продолжение:
    - строки обрабатываются в порядке возрастания topreality_id
    - Ctrl+C -- в конце печатается id последней успешно обработанной
      строки; следующий запуск делать с --start-id <тот id + 1>
    - --dry-run ничего не пишет в БД, только печатает, что было бы сделано
    - --limit ограничивает число строк за один прогон

Использование:
    python3 topreality_backfill.py --dry-run --limit 5
    python3 topreality_backfill.py
    python3 topreality_backfill.py --start-id 12346
    python3 topreality_backfill.py --limit 200 --start-id 12346
"""

import os
import sys
import time
import logging
import argparse
from datetime import datetime

import requests
import pymysql
from config import DB_CONFIG

from topReality import fetch_detail

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("topreality_backfill")


def fetch_rows_to_process(conn, start_id: int, limit):
    query = """
        SELECT topreality_id, ad_id, source_url
          FROM topreality
         WHERE full_description IS NULL
           AND topreality_id >= %s
         ORDER BY topreality_id ASC
    """
    params = [start_id]
    if limit:
        query += " LIMIT %s"
        params.append(limit)

    with conn.cursor(pymysql.cursors.Cursor) as cursor:
        cursor.execute(query, params)
        return cursor.fetchall()


def update_row(conn, topreality_id: int, detail: dict):
    with conn.cursor() as cursor:
        cursor.execute(
            """
            UPDATE topreality
               SET full_description = %s,
                   latitude = %s,
                   longitude = %s
             WHERE topreality_id = %s
            """,
            (
                detail["full_description"] or "",
                detail["latitude"],
                detail["longitude"],
                topreality_id,
            ),
        )
    conn.commit()


def main():
    parser = argparse.ArgumentParser(
        description="Одноразовый backfill full_description/координат/фото для старых строк topreality"
    )
    parser.add_argument("--start-id", type=int, default=0)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--delay", type=float, default=1.5)
    args = parser.parse_args()

    if not DB_CONFIG:
        log.error("DB_CONFIG не задан в config.py")
        sys.exit(1)

    conn = pymysql.connect(**DB_CONFIG)
    session = requests.Session()

    rows = fetch_rows_to_process(conn, args.start_id, args.limit)
    log.info("К обработке: %d строк (start_id=%d, limit=%s, dry_run=%s)",
             len(rows), args.start_id, args.limit, args.dry_run)

    processed = 0
    last_ok_id = None

    try:
        for topreality_id, ad_id, source_url in rows:
            log.info("Обрабатываю topreality_id=%s ad_id=%s url=%s",
                      topreality_id, ad_id, source_url)

            try:
                detail = fetch_detail(source_url, ad_id, session, download=not args.dry_run)
            except Exception as e:
                log.error("topreality_id=%s: неожиданная ошибка разбора: %s", topreality_id, e)
                time.sleep(args.delay)
                continue

            if args.dry_run:
                desc_preview = (detail["full_description"] or "")[:120]
                log.info(
                    "[DRY-RUN] topreality_id=%s: описание=%r... lat=%s lon=%s фото_ссылок=%d",
                    topreality_id, desc_preview, detail["latitude"], detail["longitude"],
                    len(detail["photos"]),
                )
            else:
                try:
                    update_row(conn, topreality_id, detail)
                except Exception as e:
                    log.error("topreality_id=%s: ошибка записи в БД: %s", topreality_id, e)
                    conn.rollback()
                    time.sleep(args.delay)
                    continue

            processed += 1
            last_ok_id = topreality_id
            time.sleep(args.delay)

    except KeyboardInterrupt:
        log.warning("Прервано пользователем (Ctrl+C).")

    finally:
        conn.close()

    log.info("=" * 80)
    log.info("Обработано строк: %d", processed)
    if last_ok_id is not None:
        log.info(
            "Последний успешно обработанный topreality_id = %d. "
            "Чтобы продолжить: --start-id %d",
            last_ok_id, last_ok_id + 1,
        )
    else:
        log.info("Ни одной строки не было успешно обработано.")


if __name__ == "__main__":
    main()