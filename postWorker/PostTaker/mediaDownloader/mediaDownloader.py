import os
import uuid
import mimetypes
from pathlib import Path

import pymysql
from telethon import TelegramClient
from telethon.tl.types import MessageMediaPhoto

import uuid
from pathlib import Path

import pymysql
from telethon import TelegramClient
from telethon.tl.types import MessageMediaPhoto, PeerChannel

from config import DB_CONFIG, TG_API_HASH, TG_API_HASH, TG_API_ID

# ==============================================================
# CONFIG
# ==============================================================

TABLES = [
    "products",
    "jobs",
    "neighbors",
    "ads_thingspost",
    "ads_jobpost",
    "ads_neighborpost",
]


BASE_DIR = Path(__file__).resolve().parent

# Абсолютный путь к session без расширения .session
TG_SESSION = BASE_DIR / "PostParser"

MEDIA_ROOT = Path("/var/www/app/pusto/pusto/media")
PREVIEW_DIR = MEDIA_ROOT / "telegram_previews"

# Если не хочешь обновлять путь в БД — поставь None
PREVIEW_PATH_FIELD = "preview_image"


# ==============================================================
# HELPERS
# ==============================================================

def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def get_connection():
    return pymysql.connect(**DB_CONFIG)


def column_exists(cursor, table_name: str, column_name: str) -> bool:
    sql = """
        SELECT COUNT(*) AS cnt
        FROM information_schema.columns
        WHERE table_schema = %s
          AND table_name = %s
          AND column_name = %s
    """
    cursor.execute(sql, (DB_CONFIG["database"], table_name, column_name))
    row = cursor.fetchone()
    return bool(row and row["cnt"] > 0)


def fetch_rows_without_preview(cursor, table_name: str):
    sql = f"""
        SELECT id, chat_id, photo_id
        FROM `{table_name}`
        WHERE chat_id IS NOT NULL
          AND chat_id != ''
          AND photo_id IS NOT NULL
          AND photo_id != ''
          AND has_photo = 1
          AND (`{PREVIEW_PATH_FIELD}` IS NULL OR `{PREVIEW_PATH_FIELD}` = '')
        ORDER BY id ASC
    """
    cursor.execute(sql)
    return cursor.fetchall()


def update_preview_path(cursor, table_name: str, row_id: int, rel_path: str):
    sql = f"""
        UPDATE `{table_name}`
        SET `{PREVIEW_PATH_FIELD}` = %s
        WHERE id = %s
    """
    cursor.execute(sql, (rel_path, row_id))


def normalize_telegram_chat_id(chat_id: int) -> int:
    """
    Приводит chat_id к формату канала/супергруппы Telegram.
    """
    chat_id = int(chat_id)

    if str(chat_id).startswith("-100"):
        return chat_id

    if chat_id < 0:
        return chat_id

    return int(f"-100{chat_id}")


async def resolve_entity(client, chat_id: int):
    normalized_id = normalize_telegram_chat_id(chat_id)

    try:
        return await client.get_entity(normalized_id)
    except Exception:
        pass

    try:
        raw_id = abs(int(chat_id))
        return await client.get_entity(PeerChannel(raw_id))
    except Exception:
        pass

    return None

def build_unique_filename(table_name: str, row_id: int, chat_id: int, photo_id: int, ext: str) -> str:
    token = uuid.uuid4().hex[:10]
    return f"{table_name}_{row_id}_{chat_id}_{photo_id}_{token}{ext}"


async def download_preview_for_row(client, row: dict, table_name: str) -> str | None:
    """
    Скачивает именно превью, а не оригинал.
    Для Telethon:
      thumb=-1  -> взять миниатюру / preview максимального доступного размера,
                   но не полный оригинал.
    """
    row_id = row["id"]
    chat_id = row["chat_id"]
    photo_id = row["photo_id"]

    entity = await resolve_entity(client, chat_id)
    if not entity:
        print(f"[{table_name}:{row_id}] entity not found for chat_id={chat_id}")
        return None

    try:
        message = await client.get_messages(entity, ids=int(photo_id))
    except Exception as e:
        print(f"[{table_name}:{row_id}] get_messages failed for chat_id={chat_id}, photo_id={photo_id}: {e}")
        return None

    if not message:
        print(f"[{table_name}:{row_id}] message not found")
        return None

    if not message.media or not isinstance(message.media, MessageMediaPhoto):
        print(f"[{table_name}:{row_id}] message has no photo media")
        return None

    temp_name = PREVIEW_DIR / f"tmp_{uuid.uuid4().hex}"

    try:
        # ВАЖНО:
        # thumb=-1 => скачать не оригинал, а превью / thumbnail
        downloaded = await client.download_media(
            message=message,
            file=str(temp_name),
            thumb=-1,
        )
    except Exception as e:
        print(f"[{table_name}:{row_id}] download_media failed: {e}")
        return None

    if not downloaded:
        print(f"[{table_name}:{row_id}] preview download returned empty result")
        return None

    downloaded_path = Path(downloaded)
    ext = downloaded_path.suffix.lower() or ".jpg"

    unique_name = build_unique_filename(
        table_name=table_name,
        row_id=row_id,
        chat_id=chat_id,
        photo_id=photo_id,
        ext=ext,
    )

    final_path = PREVIEW_DIR / unique_name

    try:
        downloaded_path.rename(final_path)
    except Exception as e:
        print(f"[{table_name}:{row_id}] file rename failed: {e}")
        return None

    rel_path = final_path.relative_to(MEDIA_ROOT).as_posix()
    print(f"[{table_name}:{row_id}] saved preview -> {rel_path}")
    return rel_path


# ==============================================================
# MAIN
# ==============================================================

async def main():
    ensure_dir(PREVIEW_DIR)

    client = TelegramClient(str(TG_SESSION), TG_API_ID, TG_API_HASH)

    await client.start()

    me = await client.get_me()

    print(f"AUTHORIZED: {me.id} @{me.username}")

    conn = get_connection()

    try:
        with conn.cursor() as cursor:
            for table_name in TABLES:
                print(f"\n=== Processing table: {table_name} ===")

                has_preview_column = False
                if PREVIEW_PATH_FIELD:
                    has_preview_column = column_exists(cursor, table_name, PREVIEW_PATH_FIELD)
                    if not has_preview_column:
                        print(f"[{table_name}] column `{PREVIEW_PATH_FIELD}` not found, DB update will be skipped")

                rows = fetch_rows_without_preview(cursor, table_name)

                if not rows:
                    print(f"[{table_name}] nothing to process")
                    continue

                for row in rows:
                    rel_path = await download_preview_for_row(client, row, table_name)

                    if rel_path and has_preview_column:
                        try:
                            update_preview_path(cursor, table_name, row["id"], rel_path)
                            conn.commit()
                        except Exception as e:
                            conn.rollback()
                            print(f"[{table_name}:{row['id']}] DB update failed: {e}")

    finally:
        conn.close()
        await client.disconnect()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())