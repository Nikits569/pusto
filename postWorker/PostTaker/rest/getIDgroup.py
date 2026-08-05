from telethon import TelegramClient
import asyncio
from config import api_id, api_hash, SESSION

client = TelegramClient(SESSION, api_id, api_hash)

async def main():
    await client.start()
    # Вместо 'hack_kosice' подставь username группы или ссылку на чат (например, 't.me/hack_kosice')
    entity = await client.get_entity('t.me/austriadruzi')
    print(f"ID группы/чата: {entity.id}")

asyncio.run(main())
