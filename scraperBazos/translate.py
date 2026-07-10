from deep_translator import GoogleTranslator
import pymysql
from config import DB_CONFIG

conn = pymysql.connect(**DB_CONFIG)

try:
    with conn.cursor(pymysql.cursors.DictCursor) as cursor:

        cursor.execute("""
            SELECT id, text_sk
            FROM bazos
            WHERE
                (text_en IS NULL OR text_en = '')
                OR
                (text IS NULL OR text = '')

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
                    UPDATE bazos
                    SET
                        text=%s,
                        text_en=%s
                    WHERE id=%s
                    """,
                    (
                        text_ua,
                        text_en,
                        row["id"]
                    )
                )

                processed += 1

                if processed % batch_size == 0:
                    conn.commit()
                    print(f"Committed {processed} records")

                print(f"Translated {row['id']}")

            except Exception as e:
                print(f"Translate error {row['id']}: {e}")

        # финальный коммит для остатка
        conn.commit()
        print(f"Done. Total translated: {processed}")

finally:
    conn.close()