import os
import asyncio
import threading
from telethon import TelegramClient

_runner = None


class TelegramRunner:
    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self._ready = threading.Event()
        self._start_error = None

        self.thread = threading.Thread(target=self._thread_main, daemon=True)
        self.thread.start()

        # ждём инициализацию
        self._ready.wait()

        # если старт не удался — сразу падаем (чтобы ты видел причину)
        if self._start_error:
            raise self._start_error

    def _thread_main(self):
        asyncio.set_event_loop(self.loop)

        try:
            api_id = int(os.environ["TG_API_ID"])
            api_hash = os.environ["TG_API_HASH"]
            session_path = os.environ["TG_SESSION_PATH"]
        except KeyError as e:
            self._start_error = RuntimeError(f"Missing env var: {e}")
            self._ready.set()
            return

        self.client = TelegramClient(session_path, api_id, api_hash)

        async def _start():
            await self.client.connect()
            if not await self.client.is_user_authorized():
                raise RuntimeError("Telegram session not authorized (нужно один раз залогиниться)")
            return True

        try:
            # ВАЖНО: тут блокируемся, пока реально не подключится/авторизуется
            self.loop.run_until_complete(_start())
            self._ready.set()
        except Exception as e:
            self._start_error = e
            self._ready.set()
            return

        self.loop.run_forever()

    def run(self, coro, timeout=20):
        fut = asyncio.run_coroutine_threadsafe(coro, self.loop)
        return fut.result(timeout=timeout)


def get_runner() -> TelegramRunner:
    global _runner
    if _runner is None:
        _runner = TelegramRunner()
    return _runner