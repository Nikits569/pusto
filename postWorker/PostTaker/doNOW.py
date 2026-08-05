import os
import pymysql
from parser.config import DB_CONFIG

# ==============================================================
# MAIN
# ==============================================================
connection = pymysql.connect(**DB_CONFIG)

try:
    with connection.cursor() as cursor:

        path = '/var/www/app/pusto/postWorker/PostTaker/media/telegram_previews/'

        cursor.execute("""
            SELECT id, chat_id, message_id FROM base 
            WHERE timePost >= '2026-07-16'
        """)

        for i in cursor.fetchall():
            old_dir = os.path.join(path, str(i['id']))

            if not os.path.exists(old_dir):
                continue

            # Если это старый "плоский" формат — файлы лежат прямо в old_dir
            entries = os.listdir(old_dir)
            photo_files = sorted([
                f for f in entries
                if os.path.isfile(os.path.join(old_dir, f))
                and f.lower().endswith(('.jpg', '.jpeg', '.png'))
            ])

            if not photo_files:
                # либо папка уже в новом формате (внутри подпапка), либо пустая — пропускаем
                continue

            new_subdir_name = f"{i['chat_id']}_{i['message_id']}"
            new_subdir = os.path.join(old_dir, new_subdir_name)

            os.makedirs(new_subdir, exist_ok=True)

            print(f"Migrating id={i['id']}: {len(photo_files)} files -> {new_subdir}")

            for idx, filename in enumerate(photo_files, start=1):
                old_file_path = os.path.join(old_dir, filename)
                new_file_path = os.path.join(new_subdir, f"{idx}.jpg")
                os.rename(old_file_path, new_file_path)
                print(f"  {filename} -> {new_file_path}")

except Exception as e:
    print(e)

finally:
    connection.close()