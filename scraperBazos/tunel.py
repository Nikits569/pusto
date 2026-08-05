import pymysql
from config import DB_CONFIG, PLACEHOLDER_HASH
from django.utils.text import slugify
from unidecode import unidecode
import traceback
from typing import Union
import hashlib
import os
import sys
from urllib.parse import urlparse
import requests

conn = pymysql.connect(**DB_CONFIG)

inserted = 0
skipped = 0

categories = {
    12: "взуття",
    13: "чоловічий одяг",
    14: "жіночий одяг",
    15: "аксесуари",
    16: "телефони",
    17: "ноутбуки/пк",
    18: "аудіо техніка",
    19: "ігрові приставки",
    20: "меблі",
    21: "косметика",
    22: "парфумерія",
    23: "велосипеди",
    24: "музичні інструменти",
    25: "електросамокати",
    26: "монітори",
    27: "книги",
    28: "спорт",
    29: "холодильники",
    30: "побутова техніка",
    31: "інше",
}

categories_id = {
    "bycycle": 23,
    "electric_scooter": 25,
    "phone": 16,
    "monitor": 26,
    "PC": 17,
    "notebook": 17,
    "fridge": 29

}

CACHE_DIR = "cache"


def _cache_key(url: str) -> str:
    """Хеш от URL — используется как имя файла в кеше."""
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def _guess_extension(url: str, content_type: str = "") -> str:
    """Пытаемся определить расширение файла — сперва по URL, потом по content-type."""
    path = urlparse(url).path
    ext = os.path.splitext(path)[1]
    if ext:
        return ext

    mapping = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }
    return mapping.get(content_type.split(";")[0].strip(), ".bin")


def get_cached_photo(url: str) -> Union[str, bool]:
    photo_cash = _cache_key(url)

    cursor.execute("SELECT id FROM bazos WHERE photo_cash = %s", (photo_cash,))

    if cursor.fetchone():
        return False
    else:
        return photo_cash


try:
    with conn.cursor() as cursor:

        cursor.execute("SELECT * FROM bazos")
        rows = cursor.fetchall()

        print(f"FOUND {len(rows)} RECORDS")

        for row in rows:
                photo_cash = get_cached_photo(row["image_url"])
                if photo_cash == PLACEHOLDER_HASH:
                    continue  # заглушка "нет фото" — не проверяем на дубликат, просто продолжаем обработку

                if photo_cash is False:
                    print('duplicate hash SKIP')
                    skipped += 1
                    continue

                text = row["text"] or row["text_sk"] or ""
                text_en = row["text_en"] or text
                text_sk = row["text_sk"] or text

                location = row["adress"] or None

                title = text[:25].strip()
                title_sk = row["text_sk"][:25].strip()
                title_en = text_en[:25].strip()

                if row["category"] == "reality":

                    cursor.execute("""
                        SELECT 1
                        FROM ads_neighborpost
                        WHERE id_bazos=%s
                        LIMIT 1
                    """, (row["bazos_id"],))

                    inserted += 1
                    print(f"INSERTED NEIGHBOR {row['bazos_id']}")

                    if cursor.fetchone():
                        skipped += 1
                        continue

                    cursor.execute(
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
                                adress
                            )
                            VALUES (
                                %s,%s,%s,%s,%s,%s,%s,%s,
                                %s,%s,%s,%s,%s,%s,%s,%s,%s,
                                %s,%s,%s,%s,%s,%s,%s,%s,%s,
                                %s,%s,%s,%s,%s,%s
                            )
                            """,
                            (
                            "bazos",

                            row["created_at"],

                            title,
                            slugify(unidecode(title_sk)),

                            row["text"],      # основной текст = украинский

                            row["city"],
                            "rent",
                            row["price"],

                            row["text_en"],
                            title_en,

                            row["text_sk"],         # словацкий
                            title_sk,

                            row["rooms"],

                            row["bazos_id"],
                            row["image_url"],
                            row["source_url"],
                            'bazos',                   # source_bazos

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

                             "",
                            location
                        )
                    )

                if row["type"] == "sell" or row["type"] == "buy":
                        cursor.execute("""
                                    SELECT 1
                                    FROM ads_thingspost
                                    WHERE id_bazos=%s
                                    LIMIT 1
                                """, (row["bazos_id"],))

                        if cursor.fetchone():
                            skipped += 1
                            continue

                        product_category = categories_id.get(row["category"].strip(), 31)

                        cursor.execute("""
                        INSERT INTO ads_thingspost (
        
                            telegram_username,
                            created_at,
        
                            title,
                            slug_title,
                            text,
                            city,
                            
                            caseType,
                            price,
        
                            text_en,
                            title_en,
        
                            text_sk,
                            title_sk,
        
                            productCategory,
        
                            id_bazos,
                            img_bazos,
                            link_bazos,
                            source,
        
                            email,
                            is_verified,
        
                            status,
                            private_status,
        
                            withoutRegister,
                            tg_deleted,
                            email_confirmed,
        
                            chat_id
        
                        )
                        VALUES (
                            %s,%s,%s,%s,%s,%s,
                            %s, %s,
                            %s,%s,
                            %s,%s,
                            %s,%s,
                            %s,%s,%s,%s,
                            %s,%s,
                            %s,%s,
                            %s,%s,
                            %s
                        )
                        """, (

                            "bazos",
                            row["created_at"],

                            title,
                            slugify(unidecode(title_sk)),
                            text,
                            row["city"],

                            'sell_category',
                            row["price"],

                            text_en,
                            title_en,

                            text_sk,
                            title_sk,

                            product_category,

                            row["bazos_id"],
                            row["image_url"],
                            row["source_url"],
                            "bazos",

                            "bazos@bazos.sk",
                            0,

                            "active",
                            "common",

                            1,
                            0,
                            1,

                            ""

                        ))
                        inserted += 1

                        print(
                            f"INSERTED | "
                            f"{row['bazos_id']} | "
                            f"{row['city']} | "
                            f"{title_sk[:40]}"
                        )

                print("=" * 50)
                print(f"INSERTED: {inserted}")
                print(f"SKIPPED : {skipped}")
                print("=" * 50)

except Exception as e:

    skipped += 1
    print("=" * 80)
    print(f"ERROR bazos_id={row['bazos_id']}")
    print(e)
    traceback.print_exc()
    print("ROW:")
    print(row)
    print("=" * 80)


finally:
    conn.commit()
    conn.close()
    print("DB connection closed")



