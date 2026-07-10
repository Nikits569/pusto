import asyncio
import pymysql

from config import DB_CONFIG

# Асинхронная блокировка для защиты от одновременной записи в БД.
# Нужна, чтобы несколько задач не писали в таблицы одновременно.
db_lock = asyncio.Lock()

# Подключение к MySQL.
# Здесь хранятся все спарсенные объявления и хэши изображений.
conn = pymysql.connect(**DB_CONFIG)

# Общий курсор для SQL-запросов.
cursor = conn.cursor()