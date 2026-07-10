#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Переводчик описаний reality: text_sk (оригинал, словацкий) ->
    text     (перевод на украинский)
    text_en  (перевод на английский)

Логика и конвенция полей -- как в аналогичном скрипте для topreality
(translate_topreality.py). Первичный ключ (auto_increment) в реальной
таблице называется reality_id (не id!), поэтому UPDATE идёт по нему.

Запуск:
    python3 translate_reality.py

Через cron (например, раз в 20-30 минут, чтобы не упираться в лимиты
Google Translate):
    */20 * * * * cd /var/www/app/pusto/scraperReality && \
        /var/www/app/pusto/pusto/venv/bin/python3 -u translate_reality.py \
        >> /var/log/reality_translate.log 2>&1
"""

from deep_translator import GoogleTranslator
import pymysql
from config import DB_CONFIG

conn = pymysql.connect(**DB_CONFIG)

try:
    with conn.cursor(pymysql.cursors.DictCursor) as cursor:

        cursor.execute("""
            SELECT reality_id, text_sk
            FROM reality

        """)

        rows = cursor.fetchall()

        print(f"Need translate: {len(rows)}")

        translator_uk = GoogleTranslator(
            source="sk",
            target="uk"
        )

        translator_en = GoogleTranslator(
            source="sk",
            target="en"
        )

        batch_size = 100
        processed = 0

        for row in rows:
            text = row["text_sk"]

            if not text:
                continue

            try:
                text_ua = translator_uk.translate(text)
                text_en = translator_en.translate(text)

                cursor.execute(
                    """
                    UPDATE reality
                    SET
                        text=%s,
                        text_en=%s
                    WHERE reality_id=%s
                    """,
                    (
                        text_ua,
                        text_en,
                        row["reality_id"]
                    )
                )

                processed += 1

                if processed % batch_size == 0:
                    conn.commit()
                    print(f"Committed {processed} records")

                print(f"Translated {row['reality_id']}")

            except Exception as e:
                print(f"Translate error {row['reality_id']}: {e}")

        # финальный коммит для остатка
        conn.commit()
        print(f"Done. Total translated: {processed}")

finally:
    conn.close()