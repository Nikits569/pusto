# ads/telegram_client.py
import os
import asyncio
import threading
from telethon import TelegramClient

API_ID = int(os.environ.get("TG_API_ID", "0"))
API_HASH = os.environ.get("TG_API_HASH", "")
SESSION_PATH = os.environ.get("TG_SESSION_PATH", "tg_django_session")

class TelegramRunner:
    def __init__(self):
        if not API_ID or not API_HASH:
            raise RuntimeError("TG_API_ID / TG_API_HASH not set")

        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

        self.client = TelegramClient(SESSION_PATH, API_ID, API_HASH, loop=self.loop)

        # ВОТ ЭТО ОБЯЗАТЕЛЬНО
        self.sem = asyncio.Semaphore(3)

        fut = asyncio.run_coroutine_threadsafe(self._connect(), self.loop)
        fut.result(timeout=30)

    def _run_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    async def _connect(self):
        await self.client.connect()
        if not await self.client.is_user_authorized():
            raise RuntimeError("Telegram session not authorized")
        return True

    def run(self, coro, timeout=20):
        fut = asyncio.run_coroutine_threadsafe(coro, self.loop)
        return fut.result(timeout=timeout)

_runner = None
def get_runner() -> TelegramRunner:
    global _runner
    if _runner is None:
        _runner = TelegramRunner()
    return _runner