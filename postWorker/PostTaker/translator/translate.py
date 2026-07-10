from deep_translator import GoogleTranslator
import pymysql
import time
from config import *

# SK EN

print("START")

POST_TABLES = [
    "ads_thingspost",
    "ads_neighborpost",
    # "ads_jobpost",
]


def translate_text(text, target_lang):
    if not text or len(text.strip()) < 3:
        return text

    try:
        return GoogleTranslator(
            source='auto',
            target=target_lang
        ).translate(text)

    except Exception as e:
        print(f"Translate error [{target_lang}]: {e}")
        return text


def process_table(connection, table):
    with connection.cursor() as cursor:

        query = f"""
            SELECT
                id,
                title,
                text,

                title_en,
                text_en,

                title_sk,
                text_sk

            FROM {table}

            WHERE
                (title_en IS NULL OR title_en = '')
                OR
                (text_en IS NULL OR text_en = '')
                OR
                (title_sk IS NULL OR title_sk = '')
                OR
                (text_sk IS NULL OR text_sk = '')

            ORDER BY created_at DESC
        """

        cursor.execute(query)
        rows = cursor.fetchall()

        print(f"\n📦 {table}: {len(rows)} rows")

        for row in rows:
            try:
                title = row["title"] or ""
                text = row["text"] or ""

                # EN
                title_en = row["title_en"] or translate_text(title, "en")
                text_en = row["text_en"] or translate_text(text[:4000], "en")

                # SK
                title_sk = row["title_sk"] or translate_text(title, "sk")
                text_sk = row["text_sk"] or translate_text(text[:4000], "sk")

                update_query = f"""
                    UPDATE {table}
                    SET
                        title_en=%s,
                        text_en=%s,
                        title_sk=%s,
                        text_sk=%s
                    WHERE id=%s
                """

                cursor.execute(
                    update_query,
                    (
                        title_en,
                        text_en,
                        title_sk,
                        text_sk,
                        row["id"]
                    )
                )

                connection.commit()

                print(f"✔ {table} id={row['id']}")

                # анти-бан
                time.sleep(0.4)

            except Exception as e:
                print(f"❌ {table} id={row['id']} error: {e}")
                connection.rollback()


def main():
    connection = pymysql.connect(**DB_CONFIG)

    try:
        for table in POST_TABLES:
            process_table(connection, table)

    finally:
        connection.close()


if __name__ == "__main__":
    main()