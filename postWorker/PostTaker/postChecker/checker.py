"""
Объединённый чекер объявлений.

Для каждой post-таблицы (ads_thingspost, ads_neighborpost, ads_jobpost)
последовательно делает две вещи:

  ЭТАП 1. Проверка через Telegram (Telethon):
      Для каждой строки смотрит, существует ли ещё сообщение в чате.
      Если сообщение удалено в Telegram - удаляет строку из post-таблицы,
      из первоисточника (products/jobs/neighbors) и из base.

  ЭТАП 2. Проверка дублей по фото (среди того, что осталось после этапа 1):
      Для каждой оставшейся строки берёт главное фото
      media/telegram_previews/{chat_id}_{message_id}/1.jpg (или первое по номеру),
      считает перцептивный хеш (phash) и сравнивает попарно внутри таблицы.
      Если расстояние Хэмминга между хешами <= HASH_THRESHOLD - считает дублями.
      В каждой группе дублей оставляет запись с наименьшим id, остальные удаляет
      (тем же способом: post-таблица + первоисточник + base).

Зависимости:
    pip install telethon pymysql imagehash Pillow

ВНИМАНИЕ: удаление в обоих этапах происходит сразу, без подтверждения.
"""

import asyncio
import glob
import os
import shutil
import tempfile
from itertools import combinations

import imagehash
import pymysql
from PIL import Image
from telethon import TelegramClient, functions, types

from config import api_id, api_hash, SESSION, DB_CONFIG

# Чекер работает параллельно с основным парсером (PostParser.session),
# который постоянно держит открытой ту же сессию Telethon и периодически
# пишет в её SQLite-файл. Чтобы не ловить "database is locked" при
# конкурентной записи, чекер подключается не к живому файлу сессии,
# а к его временной копии - читать сообщения это не мешает, а конфликтов
# с парсером больше не возникает.
SESSION_FILE = f"{SESSION}.session"

POST_TABLES = [
    "ads_thingspost",
    "ads_neighborpost",
    "ads_jobpost",
]

SOURCE_TABLE_BY_POST_TABLE = {
    "ads_thingspost": "products",
    "ads_jobpost": "jobs",
    "ads_neighborpost": "neighbors",
}

# Название базовой таблицы, из которой объявления переносятся в
# ads_thingspost / ads_neighborpost. Если называется иначе - поменяй тут.
BASE_TABLE = "base"

target_chats = {
    4936692115: [None],
    1175233956: [None],
    1956832493: [None],
    2091082928: [None],
    2101692521: [None],
    1912835249: [14756],

    1386423654: [177319, 193366],

    1274583303: [51851, 51849],

    2240457831: [18915, 27, 26],
    1764112838: [112, 111, 82],

    2766446415: [None],
    5007496260: [None],
    1840072195: [None],
    3752323083: [None],
}

MEDIA_ROOT = "/var/www/app/pusto/postWorker/PostTaker/media/telegram_previews"

# Порог расстояния Хэмминга между phash-ами, при котором фото считаются
# дубликатами. Меньше = строже (только почти идентичные фото).
HASH_THRESHOLD = 5


# ---------------------------------------------------------------------------
# Общие утилиты БД
# ---------------------------------------------------------------------------

def get_all_target_chat_ids():
    return set(target_chats.keys())


def select_posts(cursor, table_name):
    sql = f"SELECT id, message_id, chat_id FROM `{table_name}` WHERE source = 'telegram'"
    cursor.execute(sql)
    return cursor.fetchall()


def count_posts(cursor, table_name):
    sql = f"SELECT COUNT(*) AS cnt FROM `{table_name}` WHERE source = 'telegram'"
    cursor.execute(sql)
    return cursor.fetchone()["cnt"]


def delete_by_chat_and_message(cursor, table_name, chat_id, message_id):
    sql = f"""
        DELETE FROM `{table_name}`
        WHERE chat_id = %s AND message_id = %s
    """
    cursor.execute(sql, (chat_id, message_id))
    return cursor.rowcount


def delete_source_from_db(cursor, post_table_name, chat_id, message_id):
    source_table = SOURCE_TABLE_BY_POST_TABLE.get(post_table_name)

    if not source_table:
        return 0

    return delete_by_chat_and_message(cursor, source_table, chat_id, message_id)


def delete_base_from_db(cursor, chat_id, message_id):
    return delete_by_chat_and_message(cursor, BASE_TABLE, chat_id, message_id)


def delete_post_everywhere(conn, cursor, table_name, chat_id, message_id):
    deleted_posts = delete_by_chat_and_message(cursor, table_name, chat_id, message_id)
    deleted_sources = delete_source_from_db(cursor, table_name, chat_id, message_id)
    deleted_base = delete_base_from_db(cursor, chat_id, message_id)
    conn.commit()
    return deleted_posts, deleted_sources, deleted_base


# ---------------------------------------------------------------------------
# Этап 1: проверка удалённых в Telegram
# ---------------------------------------------------------------------------

async def build_input_channel_map(client, needed_chat_ids):
    dialogs = await client.get_dialogs()
    result = {}

    for dialog in dialogs:
        entity = dialog.entity
        entity_id = getattr(entity, "id", None)

        if entity_id in needed_chat_ids:
            try:
                input_entity = await client.get_input_entity(entity)
                if isinstance(input_entity, types.InputPeerChannel):
                    result[entity_id] = input_entity
            except Exception:
                pass

    return result


async def check_telegram_stage(conn, client, channel_map, table_name):
    """
    Возвращает (stats, alive_rows), где alive_rows - список словарей
    {id, chat_id, message_id} для строк, которые НЕ были удалены на этом этапе
    (в том числе те, для которых чат не нашёлся в диалогах - их не трогаем).
    """
    stats = {
        "ok_count": 0,
        "deleted_count": 0,
        "deleted_from_db_count": 0,
        "source_deleted_from_db_count": 0,
        "base_deleted_from_db_count": 0,
        "chat_not_found_count": 0,
        "error_count": 0,
        "skipped_count": 0,
    }

    alive_rows = []

    print("\n==============================")
    print(f"ЭТАП 1 (Telegram): {table_name}")
    print("==============================")

    with conn.cursor() as cursor:
        total_in_db = count_posts(cursor, table_name)
        print(f"[{table_name}] Всего строк в БД: {total_in_db}")

        rows = select_posts(cursor, table_name)
        print(f"[{table_name}] Строк реально получено SELECT'ом: {len(rows)}")

        for row in rows:
            db_id = row["id"]
            raw_chat_id = row["chat_id"]
            raw_message_id = row["message_id"]

            if raw_chat_id is None or str(raw_chat_id).strip() == "":
                print(f"[{table_name}] ПРОПУСК | ID={db_id} | пустой chat_id")
                stats["skipped_count"] += 1
                continue

            if raw_message_id is None or str(raw_message_id).strip() == "":
                print(f"[{table_name}] ПРОПУСК | ID={db_id} | пустой message_id")
                stats["skipped_count"] += 1
                continue

            try:
                chat_id = int(raw_chat_id)
                message_id = int(raw_message_id)
            except Exception:
                print(f"[{table_name}] ПРОПУСК | ID={db_id} | chat_id/message_id не int")
                stats["skipped_count"] += 1
                continue

            print(
                f"[{table_name}] --- Проверка "
                f"ID={db_id}, chat_id={chat_id}, message_id={message_id}, "
                f"https://t.me/c/{chat_id}/{message_id}"
            )

            input_channel = channel_map.get(chat_id)

            if not input_channel:
                print(f"[{table_name}] ЧАТ НЕ НАЙДЕН В ДИАЛОГАХ | ID={db_id}")
                stats["chat_not_found_count"] += 1
                # чат не нашли - не можем проверить удаление, но и не удаляем;
                # такую строку всё равно пускаем на этап дедупа по фото
                alive_rows.append({"id": db_id, "chat_id": chat_id, "message_id": message_id})
                continue

            try:
                result = await client(
                    functions.channels.GetMessagesRequest(
                        channel=input_channel,
                        id=[types.InputMessageID(id=message_id)],
                    )
                )

                messages = getattr(result, "messages", [])

                is_deleted = False

                if not messages:
                    is_deleted = True
                elif isinstance(messages[0], types.MessageEmpty):
                    is_deleted = True

                if is_deleted:
                    print(f"[{table_name}] ОБЪЯВЛЕНИЕ УДАЛЕНО В TELEGRAM | ID={db_id}")

                    deleted_posts, deleted_sources, deleted_base = delete_post_everywhere(
                        conn=conn,
                        cursor=cursor,
                        table_name=table_name,
                        chat_id=chat_id,
                        message_id=message_id,
                    )

                    print(
                        f"[{table_name}] УДАЛЕНО ИЗ БД | "
                        f"{table_name}={deleted_posts}, "
                        f"{SOURCE_TABLE_BY_POST_TABLE.get(table_name)}={deleted_sources}, "
                        f"{BASE_TABLE}={deleted_base}"
                    )

                    stats["deleted_count"] += 1
                    stats["deleted_from_db_count"] += deleted_posts
                    stats["source_deleted_from_db_count"] += deleted_sources
                    stats["base_deleted_from_db_count"] += deleted_base
                    continue

                print(f"[{table_name}] OK | ID={db_id}")
                stats["ok_count"] += 1
                alive_rows.append({"id": db_id, "chat_id": chat_id, "message_id": message_id})

            except Exception as e:
                conn.rollback()
                print(f"[{table_name}] ОШИБКА | ID={db_id} | {e}")
                stats["error_count"] += 1

    print(f"\n--- ИТОГ ЭТАПА 1 ПО {table_name} ---")
    print(f"OK: {stats['ok_count']}")
    print(f"Удалено в Telegram: {stats['deleted_count']}")
    print(f"Удалено из post-таблицы: {stats['deleted_from_db_count']}")
    print(f"Удалено из первоисточника: {stats['source_deleted_from_db_count']}")
    print(f"Удалено из base: {stats['base_deleted_from_db_count']}")
    print(f"Чат не найден: {stats['chat_not_found_count']}")
    print(f"Ошибки: {stats['error_count']}")
    print(f"Пропущено: {stats['skipped_count']}")

    return stats, alive_rows


# ---------------------------------------------------------------------------
# Этап 2: дедуп по фото
# ---------------------------------------------------------------------------

def get_post_folder(chat_id, message_id):
    return os.path.join(MEDIA_ROOT, f"{chat_id}_{message_id}")


def _photo_sort_key(path):
    name = os.path.splitext(os.path.basename(path))[0]
    try:
        return int(name)
    except ValueError:
        return 9999


def get_main_photo_path(chat_id, message_id):
    folder = get_post_folder(chat_id, message_id)

    if not os.path.isdir(folder):
        return None

    candidates = sorted(
        glob.glob(os.path.join(folder, "*.jpg")),
        key=_photo_sort_key,
    )

    return candidates[0] if candidates else None


def compute_phash(photo_path):
    try:
        with Image.open(photo_path) as img:
            return imagehash.phash(img)
    except Exception as e:
        print(f"    ОШИБКА чтения фото {photo_path}: {e}")
        return None


def build_duplicate_groups(posts):
    """
    Простое попарное сравнение (O(n^2)). Для очень больших таблиц
    стоит заменить на предварительную группировку по префиксу хеша.
    """
    groups = []
    id_to_group = {}

    for a, b in combinations(posts, 2):
        distance = a["hash"] - b["hash"]

        if distance > HASH_THRESHOLD:
            continue

        group_a = id_to_group.get(a["id"])
        group_b = id_to_group.get(b["id"])

        if group_a is None and group_b is None:
            group = {"ids": set(), "posts": []}
            groups.append(group)
        elif group_a is not None and group_b is None:
            group = group_a
        elif group_b is not None and group_a is None:
            group = group_b
        else:
            group = group_a
            if group_b is not group_a:
                for p in group_b["posts"]:
                    if p["id"] not in group["ids"]:
                        group["ids"].add(p["id"])
                        group["posts"].append(p)
                        id_to_group[p["id"]] = group
                groups.remove(group_b)

        for p in (a, b):
            if p["id"] not in group["ids"]:
                group["ids"].add(p["id"])
                group["posts"].append(p)
                id_to_group[p["id"]] = group

    return groups


def check_photo_dedup_stage(conn, table_name, alive_rows):
    stats = {
        "hashed": 0,
        "no_photo": 0,
        "duplicate_groups": 0,
        "deleted_count": 0,
        "deleted_from_db_count": 0,
        "source_deleted_from_db_count": 0,
        "base_deleted_from_db_count": 0,
    }

    print("\n==============================")
    print(f"ЭТАП 2 (фото-дедуп): {table_name}")
    print("==============================")
    print(f"[{table_name}] Строк на входе (живых после этапа 1): {len(alive_rows)}")

    posts = []

    for row in alive_rows:
        photo_path = get_main_photo_path(row["chat_id"], row["message_id"])

        if not photo_path:
            stats["no_photo"] += 1
            continue

        phash = compute_phash(photo_path)

        if phash is None:
            continue

        posts.append({
            "id": row["id"],
            "chat_id": row["chat_id"],
            "message_id": row["message_id"],
            "photo_path": photo_path,
            "hash": phash,
        })
        stats["hashed"] += 1

    print(f"[{table_name}] Захешировано фото: {stats['hashed']}, без фото: {stats['no_photo']}")

    groups = [g for g in build_duplicate_groups(posts) if len(g["posts"]) > 1]
    stats["duplicate_groups"] = len(groups)
    print(f"[{table_name}] Найдено групп дублей: {len(groups)}")

    with conn.cursor() as cursor:
        for group in groups:
            group_posts = sorted(group["posts"], key=lambda p: p["id"])
            keep = group_posts[0]
            duplicates = group_posts[1:]

            print(
                f"[{table_name}] ГРУППА | оставляем ID={keep['id']} "
                f"(chat_id={keep['chat_id']}, message_id={keep['message_id']}, "
                f"{keep['photo_path']}), дублей в группе: {len(duplicates)}"
            )

            for dup in duplicates:
                distance = keep["hash"] - dup["hash"]
                print(
                    f"    УДАЛЯЕМ ID={dup['id']} | chat_id={dup['chat_id']}, "
                    f"message_id={dup['message_id']} | "
                    f"https://t.me/c/{dup['chat_id']}/{dup['message_id']} | "
                    f"расстояние={distance}"
                )

                deleted_posts, deleted_sources, deleted_base = delete_post_everywhere(
                    conn=conn,
                    cursor=cursor,
                    table_name=table_name,
                    chat_id=dup["chat_id"],
                    message_id=dup["message_id"],
                )

                stats["deleted_count"] += 1
                stats["deleted_from_db_count"] += deleted_posts
                stats["source_deleted_from_db_count"] += deleted_sources
                stats["base_deleted_from_db_count"] += deleted_base

    print(f"\n--- ИТОГ ЭТАПА 2 ПО {table_name} ---")
    print(f"Захешировано: {stats['hashed']}")
    print(f"Без фото: {stats['no_photo']}")
    print(f"Групп дублей: {stats['duplicate_groups']}")
    print(f"Удалено дублей: {stats['deleted_count']}")
    print(f"Удалено из post-таблицы: {stats['deleted_from_db_count']}")
    print(f"Удалено из первоисточника: {stats['source_deleted_from_db_count']}")
    print(f"Удалено из base: {stats['base_deleted_from_db_count']}")

    return stats


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

async def main():
    conn = pymysql.connect(**DB_CONFIG)

    # Копируем файл сессии во временный, чтобы не конкурировать за запись
    # с постоянно работающим парсером, который держит открытой оригинальную
    # сессию (см. комментарий у SESSION_FILE выше).
    tmp_dir = tempfile.mkdtemp(prefix="checker_session_")
    tmp_session_path = os.path.join(tmp_dir, "checker_tmp.session")

    if os.path.exists(SESSION_FILE):
        shutil.copyfile(SESSION_FILE, tmp_session_path)
    else:
        print(f"ВНИМАНИЕ: файл сессии {SESSION_FILE} не найден, будет создана новая сессия")

    client = TelegramClient(tmp_session_path, api_id, api_hash)

    await client.start()

    total_tg_stats = {
        "ok_count": 0,
        "deleted_count": 0,
        "deleted_from_db_count": 0,
        "source_deleted_from_db_count": 0,
        "base_deleted_from_db_count": 0,
        "chat_not_found_count": 0,
        "error_count": 0,
        "skipped_count": 0,
    }

    total_photo_stats = {
        "hashed": 0,
        "no_photo": 0,
        "duplicate_groups": 0,
        "deleted_count": 0,
        "deleted_from_db_count": 0,
        "source_deleted_from_db_count": 0,
        "base_deleted_from_db_count": 0,
    }

    try:
        needed_chat_ids = get_all_target_chat_ids()
        channel_map = await build_input_channel_map(client, needed_chat_ids)

        print("--- Найденные каналы ---")
        for chat_id in channel_map:
            print(f"chat_id={chat_id}")

        for table_name in POST_TABLES:
            tg_stats, alive_rows = await check_telegram_stage(conn, client, channel_map, table_name)

            for key in total_tg_stats:
                total_tg_stats[key] += tg_stats[key]

            photo_stats = check_photo_dedup_stage(conn, table_name, alive_rows)

            for key in total_photo_stats:
                total_photo_stats[key] += photo_stats[key]

        print("\n==============================")
        print("ОБЩИЙ ИТОГ (ЭТАП 1: Telegram)")
        print("==============================")
        print(f"OK: {total_tg_stats['ok_count']}")
        print(f"Удалено в Telegram: {total_tg_stats['deleted_count']}")
        print(f"Удалено из post-таблиц: {total_tg_stats['deleted_from_db_count']}")
        print(f"Удалено из первоисточников: {total_tg_stats['source_deleted_from_db_count']}")
        print(f"Удалено из base: {total_tg_stats['base_deleted_from_db_count']}")
        print(f"Чат не найден: {total_tg_stats['chat_not_found_count']}")
        print(f"Ошибки: {total_tg_stats['error_count']}")
        print(f"Пропущено: {total_tg_stats['skipped_count']}")

        print("\n==============================")
        print("ОБЩИЙ ИТОГ (ЭТАП 2: фото-дедуп)")
        print("==============================")
        print(f"Захешировано: {total_photo_stats['hashed']}")
        print(f"Без фото: {total_photo_stats['no_photo']}")
        print(f"Групп дублей: {total_photo_stats['duplicate_groups']}")
        print(f"Удалено дублей: {total_photo_stats['deleted_count']}")
        print(f"Удалено из post-таблиц: {total_photo_stats['deleted_from_db_count']}")
        print(f"Удалено из первоисточников: {total_photo_stats['source_deleted_from_db_count']}")
        print(f"Удалено из base: {total_photo_stats['base_deleted_from_db_count']}")

    finally:
        conn.close()
        await client.disconnect()
        shutil.rmtree(tmp_dir, ignore_errors=True)
        print("--- DB connection closed ---")


if __name__ == "__main__":
    asyncio.run(main())