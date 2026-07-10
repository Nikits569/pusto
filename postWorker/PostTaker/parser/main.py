import asyncio

from telethon import TelegramClient
from telethon.errors import (
    SessionPasswordNeededError,
    PhoneCodeInvalidError,
    PhoneNumberInvalidError,
)

from config import api_id, api_hash, SESSION
from chat_config import all_ids
from schema import init_db_schema
from handler import register_handlers
from db import cursor, conn

print("PostSkraper STARTED!")

# Создаём Telegram-клиент.
# Через него слушаем новые сообщения в нужных чатах.
client = TelegramClient(SESSION, api_id, api_hash)

# Регистрируем обработчики событий.
register_handlers(client)

async def main():
    # При старте проверяем и создаём таблицы, если их ещё нет.
    init_db_schema()

    await client.connect()

    if not await client.is_user_authorized():
        phone = input("Введите телефон в формате +421...: ").strip()

        try:
            sent = await client.send_code_request(phone, force_sms=True)
            print("Запрос кода отправлен.")
            print("Проверь Telegram на других устройствах, чат Verification Codes и SMS.")

            code = input("Введите код: ").strip()

            await client.sign_in(
                phone=phone,
                code=code,
                phone_code_hash=sent.phone_code_hash
            )

        except SessionPasswordNeededError:
            password = input("Введите пароль 2FA: ").strip()
            await client.sign_in(password=password)

        except PhoneCodeInvalidError:
            print("Неверный код подтверждения.")

        except PhoneNumberInvalidError:
            print("Неверный номер телефона.")
    for cid in all_ids:
        print(f" - {cid}", flush=True)

    try:
        await client.run_until_disconnected()
    finally:
        # При завершении работы закрываем курсор и соединение с БД.
        cursor.close()
        conn.close()

asyncio.run(main())