# main.py
import asyncio

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import TOKEN
from handlers import posts

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

posts.register(dp)
# тут в будушем региструируем новые dp из handlers

async def main():
    print("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())