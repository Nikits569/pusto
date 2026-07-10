"""
Дедупликация фото объявлений БЕЗ скачивания файлов.

Логика:
1. ID фото = sha256(url) — считается мгновенно, сеть не используется вообще.
2. Проверяем в MySQL, есть ли такой ID.
   - Если ДА  -> это фото уже видели раньше (текст объявления мог
                поменяться, фото — нет). Ничего не делаем.
   - Если НЕТ -> это новое фото. Просто записываем ID + URL в базу.
                Сам файл фото никогда не скачивается и не хранится —
                при необходимости показать фото используешь оригинальный URL.

Установка зависимостей:
    pip install pymysql

Перед запуском создай таблицу:

    CREATE TABLE photos (
        id VARCHAR(64) PRIMARY KEY,   -- sha256(url)
        url TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

Запуск:
    python photo_dedup.py https://example.com/photo.jpg
"""

import hashlib
import sys
from config import DB_CONFIG
import pymysql


# ---- Настройки подключения к MySQL (поправь под себя) ----
conn = pymysql.connect(**DB_CONFIG)

e1 = 'https://www.topreality.sk/topfoto/t/937/9372021-1-5.jpg?1783255110'
e2 = 'https://img.unitedclassifieds.sk/foto/MzY4eDI0MS9maWx0ZXJzOnF1YWxpdHkoODApL2p1bA==/nv-OzSr7k_fss?st=m0i58L85akmfalmNaaOXMgNNrsPtqdivMpOGawNoWw8&ts=1783255009&e=0'

def get_photo_id(url: str) -> str:
    """Уникальный ID фото = sha256 от URL. Без сети, без скачивания."""
    return hashlib.sha256(url.encode("utf-8")).hexdigest()

print(get_photo_id(e1))
print(get_photo_id(e2))

try:
    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM bazos WHERE photo_cash IS NULL")
        rows = cursor.fetchall()
        for i in rows:

            photo_hash = get_photo_id(i['image_url'])
            print(i['id'], photo_hash)
            cursor.execute(
                "UPDATE bazos SET photo_cash = %s WHERE id = %s",
                (photo_hash, i['id'])
            )
finally:
    conn.commit()
    conn.close()

