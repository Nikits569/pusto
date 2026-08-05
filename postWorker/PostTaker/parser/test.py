"""
Изолированный тест скачивания и сохранения фото из Telegram.
Не трогает БД, альбомы, дедупликацию — только download_media + запись на диск.

Настрой API_ID / API_HASH / SESSION_NAME и TARGET_CHAT_ID под себя,
запусти, и когда придёт фото (или альбом) в целевой чат — увидишь,
на каком именно шаге что падает.
"""

import asyncio
import io
import os

from telethon import TelegramClient, events
from PIL import Image
import imagehash

# ==== НАСТРОЙ ПОД СЕБЯ ====
API_ID = 27916261
API_HASH = "490e9cbc170e5863605f2766ce6cf1b3"
SESSION_NAME = "test_session"

TARGET_CHAT_ID = 5073870568  # чат, где будешь тестировать
PREVIEW_ROOT = "./test_preview"
MAX_PREVIEW_PHOTOS = 3
# ===========================

client = TelegramClient(SESSION_NAME, API_ID, API_HASH)


def pick_size(sizes):
    if not sizes:
        return None, None

    # Порядок типов Telegram thumbnail (от меньшего к большему):
    # 's' ~100px, 'm' ~320px, 'x' ~800px, 'y' ~1280px (но 'y' обычно PhotoSizeProgressive — оригинал, пропускаем)
    preferred_order = ['x', 'm', 's']  # начинаем с самого крупного НЕ-оригинального размера

    by_type = {}
    for s in sizes:
        if type(s).__name__ == "PhotoSizeProgressive":
            continue  # пропускаем оригинал — он не грузится через thumb=
        t = getattr(s, "type", None)
        by_type[t] = s

    for t in preferred_order:
        if t in by_type:
            return by_type[t], t

    # fallback — любой оставшийся не-progressive размер
    if by_type:
        t, s = next(iter(by_type.items()))
        return s, t

    return None, None


@client.on(events.NewMessage(chats=TARGET_CHAT_ID))
async def handler(event):
    msg = event.message
    print("\n" + "=" * 60)
    print(f"EVENT msg_id={msg.id} grouped_id={msg.grouped_id} has_photo={bool(msg.photo)}")

    if not msg.photo:
        print("  -> no photo, skip")
        return

    # ---- ШАГ 1: скачивание thumbnail для хэша ----
    try:
        size, label = pick_size(getattr(msg.photo, "sizes", None) or [])
        print(f"  -> STEP 1: picked size={size!r} label={label!r}")

        if not size:
            print("  -> STEP 1 FAILED: no valid sizes")
            return

        data = await event.client.download_media(msg.photo, file=bytes, thumb=size)
        print(f"  -> STEP 1: downloaded {len(data) if data else 0} bytes for hash")

        if not data:
            print("  -> STEP 1 FAILED: empty data returned")
            return

        img = Image.open(io.BytesIO(data))
        phash = str(imagehash.phash(img))
        print(f"  -> STEP 1 OK: phash={phash}")

        del data, img

    except Exception as e:
        print("  -> STEP 1 ERROR:", repr(e))
        import traceback
        traceback.print_exc()
        return

    # ---- ШАГ 2: скачивание фото среднего качества для превью ----
    try:
        print("  -> STEP 2: downloading preview (thumb=-1)...")
        preview_data = await event.client.download_media(
            msg.photo, file=bytes, thumb=-1
        )
        print(f"  -> STEP 2: downloaded {len(preview_data) if preview_data else 0} bytes for preview")

        if not preview_data:
            print("  -> STEP 2 FAILED: empty preview_data")
            return

    except Exception as e:
        print("  -> STEP 2 ERROR:", repr(e))
        import traceback
        traceback.print_exc()
        return

    # ---- ШАГ 3: сохранение на диск ----
    try:
        chat_id = event.chat_id
        message_id = msg.id
        fake_base_id = 999  # в реальном коде это cursor.lastrowid

        save_dir = os.path.join(PREVIEW_ROOT, str(fake_base_id), f"{chat_id}_{message_id}")
        print(f"  -> STEP 3: save_dir={save_dir}")

        os.makedirs(save_dir, exist_ok=True)

        file_path = os.path.join(save_dir, "1.jpg")
        with open(file_path, "wb") as f:
            f.write(preview_data)

        print(f"  -> STEP 3 OK: saved to {file_path}")
        print(f"  -> file exists: {os.path.exists(file_path)}, size: {os.path.getsize(file_path)} bytes")

    except Exception as e:
        print("  -> STEP 3 ERROR:", repr(e))
        import traceback
        traceback.print_exc()
        return

    print("  -> ALL STEPS OK")


async def main():
    await client.start()
    print("Client started. Waiting for photos in target chat...")
    print(f"Target chat id: {TARGET_CHAT_ID}")
    print(f"Preview root (absolute): {os.path.abspath(PREVIEW_ROOT)}")
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())