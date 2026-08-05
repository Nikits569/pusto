import pymysql
from config import DB_CONFIG  # если это две разные базы
from django.utils.text import slugify
from unidecode import unidecode
import traceback

# Подключение к основной базе (куда пишем ads_neighborpost)
main_conn = pymysql.connect(**DB_CONFIG)

# Подключение к базе topreality (через туннель), откуда читаем исходные данные


inserted = 0
skipped = 0

try:
    with main_conn.cursor() as src_cursor, main_conn.cursor() as dst_cursor:

        src_cursor.execute("SELECT * FROM topreality")
        rows = src_cursor.fetchall()

        print(f"FOUND {len(rows)} RECORDS")

        for row in rows:
            try:
                text = row["text"] or row["text_sk"] or ""
                text_en = row["text_en"] or text
                text_sk = row["text_sk"] or text

                location = row['adress'] or None

                title_sk = text_sk[:25].strip()
                title_en = text_en[:25].strip()

                src_cursor.execute("""
                    SELECT 1
                    FROM ads_neighborpost
                    WHERE link_bazos=%s
                    LIMIT 1
                """, (row["source_url"],))

                if src_cursor.fetchone():
                    skipped += 1
                    continue

                dst_cursor.execute(
                    """
                    INSERT INTO ads_neighborpost (
                        telegram_username,
                        created_at,
                        title,
                        slug_title,
                        text,
                        city,

                        caseType,
                        budget,

                        text_en,
                        title_en,

                        text_sk,
                        title_sk,

                        rooms,

                        id_bazos,
                        img_bazos,
                        link_bazos,
                        source,

                        my_gender,
                        neighbor_gender,
                        my_age,
                        min_age,

                        rent_period,
                        housing_type,

                        email,
                        is_verified,

                        status,
                        private_status,

                        withoutRegister,
                        tg_deleted,
                        email_confirmed,

                        chat_id,
                        
                        ad_id, 
                        
                        adress
                    )
                    VALUES (
                        %s,%s,%s,%s,%s,%s,%s,%s,
                        %s,%s,%s,%s,%s,%s,%s,%s,%s,
                        %s,%s,%s,%s,%s,%s,%s,%s,%s,
                        %s,%s,%s,%s,%s,%s,%s
                    )
                    """,
                    (
                        "topreality",

                        row["created_at"],

                        title_sk,
                        slugify(unidecode(title_sk)),

                        text,

                        row["city"],
                        "rent",
                        row["price"],

                        text_en,
                        title_en,

                        text_sk,
                        title_sk,

                        row["rooms"],

                        row["topreality_id"],
                        row["image_url"],
                        row["source_url"],
                        "topreality",  # source

                        0,
                        0,
                        18,
                        18,

                        "any",
                        "apartment",

                        "bazos@bazos.sk",
                        0,

                        "active",
                        "common",

                        1,
                        0,
                        1,

                        '',
                        row['ad_id'],

                        location,

                    )
                )

                inserted += 1
                print(f"INSERTED | {row['topreality_id']} | {row['city']} | {title_sk[:40]}")

            except Exception as e:
                skipped += 1
                print("=" * 80)
                print(f"ERROR topreality_id={row.get('topreality_id')}")
                print(e)
                traceback.print_exc()
                print("ROW:")
                print(row)
                print("=" * 80)
                continue

        print("=" * 50)
        print(f"INSERTED: {inserted}")
        print(f"SKIPPED : {skipped}")
        print("=" * 50)

except Exception as e:
    print("=" * 80)
    print("FATAL ERROR (до начала обработки строк)")
    print(e)
    traceback.print_exc()
    print("=" * 80)

finally:
    main_conn.commit()
    main_conn.close()
    print("DB connections closed")