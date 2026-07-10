import io
import time
import asyncio
import imagehash
from PIL import Image
from telethon import events
from datetime import datetime
from zoneinfo import ZoneInfo
from db import cursor, conn, db_lock
from chat_config import target_chats, infoChats, infoTopic
from helpers import pick_size, check_hash, normalization_text, extract_price, score_text, extract_rooms, remove_emoji

# Временное хранилище альбомов Telegram.
# Нужно потому, что текст и фотографии одного объявления
# могут прийти отдельными сообщениями.
albums = {}

def register_handlers(client):
    print("REGISTER HANDLERS")
    @client.on(events.NewMessage())
    async def handler(event):

        global albums

        # Получаем базовые данные о чате и сообщении.
        chat = await event.get_chat()
        chat_id = chat.id
        msg = event.message
        print(
            "EVENT",
            msg.id,
            "GROUP",
            msg.grouped_id,
            "TEXT",
            bool(msg.text)
        )
        # Для форумных чатов Telegram thread_id пока берём из reply_to_msg_id.
        thread_id = getattr(msg, "reply_to_msg_id", None)

        # Определяем, относится ли сообщение к нужной категории.
        # Учитываем и chat_id, и topic_id, если чат разбит по темам.
        type_target = None
        if chat_id not in target_chats:
            print("not target chat")
            return

        allowed_topics = target_chats[chat_id]



        # Если слушаем весь чат
        if allowed_topics == [None]:
            pass

        # Иначе проверяем topic_id
        elif thread_id not in allowed_topics:
            print("not target topic/chat")
            return

        sender = await event.get_sender()

        if sender is None:
            print("sender is None — skip")
            return

        sender_name = sender.username or "<без имени>" if sender else "<неизвестный>"
        text = msg.text or "<без текста>"

        album_id = msg.grouped_id or f"single_{msg.id}"

        # Проверяем текст по таблице forbidden.
        # Если найдено совпадение, объявление не обрабатывается.
        if text.lower() != "<без текста>":
            cursor.execute("""
                SELECT text
                FROM forbidden
                WHERE %s LIKE CONCAT('%%', LOWER(text), '%%')
                COLLATE utf8mb4_general_ci
                LIMIT 1
            """, (text.lower(),))

            row = cursor.fetchone()

            if row:
                return f"FORBIDDEN TEXT: {row['text']}"

        #if type_target == 'market':
        # Создаём запись альбома, если это первое сообщение из него.
        if album_id not in albums:
            albums[album_id] = {
                "has_photo": False,
                "photo_id": '',
                "photo_hash": '',
                "text": None,
                "price": None,
                "contact_telegram": sender_name,
                "chat_id": chat_id,
                'user_id': sender.id,
                "message_id": msg.id,
                "chat_title": infoChats[chat_id][0],
                "timePost": datetime.now(ZoneInfo("Europe/Bratislava")).strftime("%Y-%m-%d %H:%M:%S"),
                "city": None,
            }

        album = albums[album_id]

        # Если в сообщении есть фото, скачиваем только thumbnail.
        # Этого достаточно для вычисления хэша и проверки дублей.
        if msg.photo:
            size, label = pick_size(getattr(msg.photo, "sizes", None) or [])
            if not size:
                print("  -> photo but no valid sizes")
                return

            data = await event.client.download_media(msg.photo, file=bytes, thumb=size)

            img = Image.open(io.BytesIO(data))
            album['photo_hash'] = str(imagehash.phash(img))
            album['photo_id'] = msg.id
            album['has_photo'] = True
            print(f"  -> telegram://{event.chat_id}/{msg.id}/{label}")

            del data, img

        # Сохраняем текст только один раз, если он ещё не записан.
        if text != "<без текста>":

            normalized = normalization_text(text)

            if chat_id in infoTopic:
                rooms = infoTopic[chat_id]
            else:
                rooms = extract_rooms(text)

            normalized = remove_emoji(normalized)

            album['rooms'] = rooms
            album["text"] = normalized
            album["timestamp"] = time.time()
            album["city"] = infoChats[chat_id][1]
            album['price'] = extract_price(text)

            print("ALBUM TEXT:", repr(album["text"]))

            print(repr(normalized))

            await asyncio.sleep(1.5)

            print("\n=== Финальное сообщение ===")

            photo_hash = album["photo_hash"]
            text = album["text"] or "<без текста>"
            price = album["price"]

            sender = album["contact_telegram"]
            chat_id = album["chat_id"]
            user_id = album["user_id"]
            timePost = album["timePost"]
            city = album["city"]
            has_photo = album["has_photo"]
            chat_title = album["chat_title"]
            photo_id = album["photo_id"]
            rooms = album["rooms"]

            dup_result = score_text(cursor, text, 'base', user_id, photo_hash)

            print("TEXT DUP CHECK:", dup_result)
            print(text)
            print("PRICE:", price)

            if dup_result["decision"] in ("duplicate", "review"):
                print("Duplicate text — skip")
                if album_id in albums:
                    del albums[album_id]
                return

            result = check_hash(photo_hash)
            if not result:
                print("Duplicate hash — skip")
                if album_id in albums:
                    del albums[album_id]
                return

            try:
                async with db_lock:

                    cursor.execute("""
                        INSERT INTO base
                        (chat_id, message_id, user_id, photo_id, timePost,
                         chat_title, text, rooms, price, city,
                         contact_telegram, has_photo, photo_hash)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        chat_id,
                        album["message_id"],
                        user_id,
                        photo_id,
                        timePost,
                        chat_title,
                        text,
                        rooms,
                        price,
                        city,
                        sender,
                        has_photo,
                        photo_hash
                    ))

                    print("ROWCOUNT:", cursor.rowcount)
                    print("LASTROWID:", cursor.lastrowid)

                    if photo_hash:
                        print("INSERT HASH")
                        cursor.execute(
                            "INSERT INTO hashes (photo_hash) VALUES (%s)",
                            (photo_hash,)
                        )

                    conn.commit()

                    cursor.execute("""
                        SELECT id, message_id, text
                        FROM base
                        WHERE message_id = %s
                        ORDER BY id DESC
                        LIMIT 1
                    """, (album["message_id"],))

                    print("CHECK SAVED:", cursor.fetchone())

                    cursor.execute("""
                        SELECT COUNT(*) as cnt
                        FROM base
                    """)

                    print("TOTAL ROWS:", cursor.fetchone())

                    print("AFTER COMMIT")

            except Exception as e:
                conn.rollback()
                print("DB ERROR:", repr(e))

            if album_id in albums:
                del albums[album_id]
