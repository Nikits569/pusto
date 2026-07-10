import asyncio
import pymysql
from telethon import TelegramClient, functions, types
from config import api_id, api_hash, SESSION, DB_CONFIG

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

target_chats = {
    4936692115: None,
    1175233956: None,
    1386423654: 177319,
    1274583303: 51851,
    2766446415: None,
    5007496260: None,
    1386423654: 193366,
    1274583303: 51849,
    1898906800: None,
}


def get_all_target_chat_ids():
    return set(target_chats.keys())

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

    return delete_by_chat_and_message(
        cursor=cursor,
        table_name=source_table,
        chat_id=chat_id,
        message_id=message_id,
    )


def select_posts(cursor, table_name):
    sql = f"SELECT id, message_id, chat_id FROM `{table_name}`"
    cursor.execute(sql)
    return cursor.fetchall()


def count_posts(cursor, table_name):
    sql = f"SELECT COUNT(*) AS cnt FROM `{table_name}`"
    cursor.execute(sql)
    return cursor.fetchone()["cnt"]


async def delete_missing_post(conn, cursor, table_name, chat_id, message_id):
    deleted_posts = delete_by_chat_and_message(
        cursor=cursor,
        table_name=table_name,
        chat_id=chat_id,
        message_id=message_id,
    )

    deleted_sources = delete_source_from_db(
        cursor=cursor,
        post_table_name=table_name,
        chat_id=chat_id,
        message_id=message_id,
    )

    conn.commit()

    return deleted_posts, deleted_sources


async def process_table(conn, client, channel_map, table_name):
    stats = {
        "ok_count": 0,
        "deleted_count": 0,
        "deleted_from_db_count": 0,
        "source_deleted_from_db_count": 0,
        "chat_not_found_count": 0,
        "error_count": 0,
        "skipped_count": 0,
    }

    print("\n==============================")
    print(f"ТАБЛИЦА: {table_name}")
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

                    deleted_posts, deleted_sources = await delete_missing_post(
                        conn=conn,
                        cursor=cursor,
                        table_name=table_name,
                        chat_id=chat_id,
                        message_id=message_id,
                    )

                    print(
                        f"[{table_name}] УДАЛЕНО ИЗ БД | "
                        f"{table_name}={deleted_posts}, "
                        f"{SOURCE_TABLE_BY_POST_TABLE.get(table_name)}={deleted_sources}"
                    )

                    stats["deleted_count"] += 1
                    stats["deleted_from_db_count"] += deleted_posts
                    stats["source_deleted_from_db_count"] += deleted_sources
                    continue

                print(f"[{table_name}] OK | ID={db_id}")
                stats["ok_count"] += 1

            except Exception as e:
                conn.rollback()
                print(f"[{table_name}] ОШИБКА | ID={db_id} | {e}")
                stats["error_count"] += 1

    print(f"\n--- ИТОГ ПО {table_name} ---")
    print(f"OK: {stats['ok_count']}")
    print(f"Удалено в Telegram: {stats['deleted_count']}")
    print(f"Удалено из post-таблицы: {stats['deleted_from_db_count']}")
    print(f"Удалено из первоисточника: {stats['source_deleted_from_db_count']}")
    print(f"Чат не найден: {stats['chat_not_found_count']}")
    print(f"Ошибки: {stats['error_count']}")
    print(f"Пропущено: {stats['skipped_count']}")

    return stats


async def main():
    conn = pymysql.connect(**DB_CONFIG)
    client = TelegramClient(SESSION, api_id, api_hash)

    await client.start()

    total_stats = {
        "ok_count": 0,
        "deleted_count": 0,
        "deleted_from_db_count": 0,
        "source_deleted_from_db_count": 0,
        "chat_not_found_count": 0,
        "error_count": 0,
        "skipped_count": 0,
    }

    try:
        needed_chat_ids = get_all_target_chat_ids()
        channel_map = await build_input_channel_map(client, needed_chat_ids)

        print("--- Найденные каналы ---")
        for chat_id in channel_map:
            print(f"chat_id={chat_id}")

        for table_name in POST_TABLES:
            stats = await process_table(conn, client, channel_map, table_name)

            for key in total_stats:
                total_stats[key] += stats[key]

        print("\n==============================")
        print("ОБЩИЙ ИТОГ ПО ВСЕМ ТАБЛИЦАМ")
        print("==============================")
        print(f"OK: {total_stats['ok_count']}")
        print(f"Удалено в Telegram: {total_stats['deleted_count']}")
        print(f"Удалено из post-таблиц: {total_stats['deleted_from_db_count']}")
        print(f"Удалено из первоисточников: {total_stats['source_deleted_from_db_count']}")
        print(f"Чат не найден: {total_stats['chat_not_found_count']}")
        print(f"Ошибки: {total_stats['error_count']}")
        print(f"Пропущено: {total_stats['skipped_count']}")

    finally:
        conn.close()
        await client.disconnect()
        print("--- DB connection closed ---")


if __name__ == "__main__":
    asyncio.run(main())