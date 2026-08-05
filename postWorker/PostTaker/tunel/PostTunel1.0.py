import os
import sys
import pymysql
from datetime import datetime
from django.db import transaction
import traceback
from config import DB_CONFIG

# --- Django init ---
sys.path.insert(0, "/var/www/app/pusto/pusto")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pusto.settings")

import django
django.setup()

from ads.models import ThingsPost, NeighborPost, Category



# --- Source DB ---
conn = pymysql.connect(**DB_CONFIG)

SOURCE_TABLE = "base"

THINGS_CATEGORIES = {"sell_category", "buy_category"}
NEIGHBOR_CATEGORIES = {"findNeighbor", "rent"}

SKIP_MODERATION_STATUSES = {"blocked", "forbidden"}

SKIP_CATEGORIES = {
    "package",
    "forbidden_category",
    "block_category",
    "ads",
    "undefined",
    "ForAdmin",
}

def parse_move_in_date(value):
    if not value:
        return None

    value = str(value).strip()

    try:
        return datetime.strptime(
            value,
            "%d.%m.%Y"
        ).date()
    except Exception:
        pass

    try:
        return datetime.strptime(
            value,
            "%Y-%m-%d"
        ).date()
    except Exception:
        pass

    return None


def get_target_model(category):
    if category in THINGS_CATEGORIES:
        return ThingsPost

    if category in NEIGHBOR_CATEGORIES:
        return NeighborPost

    return None


def gender_map(value):
    if value is None:
        return 0

    value = str(value).strip().lower()

    mapping = {
        "male": 1,
        "man": 1,
        "m": 1,

        "female": 2,
        "woman": 2,
        "f": 2,

        "any": 0,
        "all": 0,
    }

    return mapping.get(value, 0)

def to_float_or_none(value):
    if value is None or value == "":
        return None

    try:
        return float(str(value).replace(",", "."))
    except Exception:
        return None

def housing_map(value):
    if not value:
        return "any"

    value = str(value).strip().lower()

    mapping = {
        "room": "room",
        "apartment": "apartment",
        "flat": "apartment",
        "dorm": "dorm",
        "dormitory": "dorm",
    }

    return mapping.get(value, "any")


def to_int_or_none(value):

    if value is None or value == "":
        return None

    try:
        return int(float(str(value).replace(",", ".")))
    except Exception:
        return None


try:
    with conn.cursor() as cursor:
        cursor.execute(f"""
            SELECT *
            FROM `{SOURCE_TABLE}`
            WHERE categoria IS NOT NULL
              AND categoria != ''
        """)
        rows = cursor.fetchall()

        print(f"Получено строк из `{SOURCE_TABLE}`: {len(rows)}")

        for row in rows:

            category = str(
                row.get("categoria")
                or row.get("caseType")
                or ""
            ).strip()

            if category in SKIP_CATEGORIES:
                continue

            moderation_status = (
                    row.get("moderation_status")
                    or ""
            )

            if moderation_status in SKIP_MODERATION_STATUSES:
                continue

            text = row.get("text") or ""

            if not text.strip():
                continue

            title = text[:100].strip()

            common_data = dict(
                user_id=None,
                telegram_username=row.get("contact_telegram") or "",
                telegram_id=row.get("user_id"),
                created_at=row.get("timePost"),

                title=title,
                text=text,

                city=str(row.get("city") or ""),

                source="telegram",

                chat_id=row.get("chat_id"),
                message_id=row.get("message_id"),
                photo_id=row.get("photo_id"),
                has_photo=row.get("has_photo"),

                caseType=category,

                email="telegram@bursa.sk",
                status="active",

                preview_image=row.get("preview_image"),
            )

            try:

                if category in THINGS_CATEGORIES:
                    category_id = to_int_or_none(row.get("productCategory"))
                    category = None

                    if category_id is not None:
                        category = Category.objects.filter(id=category_id).first()
                        if category is None:
                            print(
                                f"Category id={category_id} not found (chat_id={row.get('chat_id')}, message_id={row.get('message_id')})")

                    obj, created = ThingsPost.objects.get_or_create(
                        chat_id=row.get("chat_id"),
                        message_id=row.get("message_id"),
                        defaults=dict(
                            **common_data,
                            price=to_int_or_none(row.get("price")),
                            condition=row.get("condition"),
                            category=category,
                        )
                    )

                    if created:
                        print(f"ThingsPost CREATED #{obj.id}")
                    else:
                        print(f"ThingsPost EXISTS #{obj.id}")


                elif category in NEIGHBOR_CATEGORIES:

                    obj, created = NeighborPost.objects.get_or_create(
                        chat_id=row.get("chat_id"),
                        message_id=row.get("message_id"),

                        defaults=dict(
                            **common_data,

                            budget=to_int_or_none(
                                row.get("price")
                            ),

                            deposit=row.get("deposit"),

                            count_neighbors=to_int_or_none(
                                row.get("countNeighbors")
                            ),

                            my_gender=gender_map(
                                row.get("myGender")
                            ),

                            neighbor_gender=gender_map(
                                row.get("neighborGender")
                            ),

                            min_age=to_int_or_none(
                                row.get("minAge")
                            ),

                            max_age=to_int_or_none(
                                row.get("maxAge")
                            ),

                            rooms=to_float_or_none(
                                row.get("rooms")
                            ),

                            housing_type=housing_map(
                                row.get("housingType")
                            ),

                            move_in_date=parse_move_in_date(
                                row.get("moveInDate")
                            ),
                        )
                    )

                    if created:
                        print(f"NeighborPost CREATED #{obj.id}")
                    else:
                        print(f"NeighborPost EXISTS #{obj.id}")
                else:
                    print(
                        f"Категория '{category}' не подошла ни под THINGS, ни под NEIGHBOR "
                        f"(chat_id={common_data['chat_id']}, message_id={common_data['message_id']})"
                    )


            except Exception as e:

                traceback.print_exc()

                error_text = traceback.format_exc()

finally:
    conn.close()
    print("DB connection closed")