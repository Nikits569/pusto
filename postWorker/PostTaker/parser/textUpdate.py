import os
import asyncio
import pymysql

from telethon import TelegramClient, functions, types
from config import api_id, api_hash, SESSION, DB_CONFIG

async def get_message_text(client, input_entity, message_id):
    msg = await client.get_messages(
        input_entity,
        ids=message_id
    )

    if not msg:
        return None

    text = (msg.message or "").strip()

    if text:
        return text

    grouped_id = getattr(msg, "grouped_id", None)

    if not grouped_id:
        return None

    ids = list(range(max(1, message_id - 20), message_id + 20))

    messages = await client.get_messages(
        input_entity,
        ids=ids
    )

    for m in messages:
        if not m:
            continue

        if getattr(m, "grouped_id", None) != grouped_id:
            continue

        candidate = (m.message or "").strip()

        if candidate:
            return candidate

    return None

async def build_input_channel_map(client):
    dialogs = await client.get_dialogs()

    result = {}

    for dialog in dialogs:
        entity = dialog.entity
        entity_id = getattr(entity, "id", None)

        try:
            input_entity = await client.get_input_entity(entity)

            result[entity_id] = input_entity

            print(
                "MAP:",
                entity_id,
                type(input_entity).__name__
            )

        except Exception as e:
            print("MAP ERROR", entity_id, e)

    return result


async def main():
    conn = pymysql.connect(**DB_CONFIG)
    cursor = conn.cursor()

    client = TelegramClient(SESSION, api_id, api_hash)

    try:
        await client.start()

        channel_map = await build_input_channel_map(client)

        cursor.execute("""
            SELECT id, chat_id, message_id
            FROM ads_neighborpost
            WHERE chat_id IS NOT NULL
              AND chat_id <> ''
              AND message_id IS NOT NULL
              AND message_id <> ''
        """)

        rows = cursor.fetchall()

        print(f"FOUND {len(rows)} ROWS")

        for row in rows:

            db_id = row["id"]

            try:
                chat_id = int(row["chat_id"])
                message_id = int(row["message_id"])
            except (ValueError, TypeError):
                print(
                    f"BAD ROW id={db_id} "
                    f"chat_id={row['chat_id']} "
                    f"message_id={row['message_id']}"
                )
                continue

            input_entity = channel_map.get(chat_id)

            if not input_entity:
                print(f"CHAT NOT FOUND {chat_id}")
                continue

            try:

                text = await get_message_text(
                    client,
                    input_entity,
                    message_id
                )

                if not text:
                    msg = await client.get_messages(
                        input_entity,
                        ids=message_id
                    )

                    print(
                        f"NO TEXT id={db_id} "
                        f"chat={chat_id} "
                        f"msg={message_id} "
                        f"grouped_id={getattr(msg, 'grouped_id', None)} "
                        f"text={repr(msg.message)} "
                        f"media={type(msg.media).__name__ if msg and msg.media else None}"
                    )
                    continue

                cursor.execute(
                    """
                    UPDATE ads_neighborpost
                    SET text=%s
                    WHERE id=%s
                    """,
                    (text, db_id)
                )

                conn.commit()

                print(
                    f"UPDATED {db_id} "
                    f"chat={chat_id} "
                    f"msg={message_id} "
                    f"text={text[:50]}"
                )

            except Exception as e:
                print(
                    f"ERROR {db_id} "
                    f"chat={chat_id} "
                    f"msg={message_id} "
                    f"{e}"
                )

    finally:
        conn.close()
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())

