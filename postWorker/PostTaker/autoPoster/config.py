import os
import pymysql
from dotenv import load_dotenv

load_dotenv("../../../.env")

DB_CONFIG = {
    "host": os.environ.get("DB_HOST"),
    "port": int(os.environ.get("DB_PORT")),
    "user": os.environ.get("DB_USER"),
    "password": os.environ.get("DB_PASSWORD"),
    "database": os.environ.get("DB_NAME"),
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
    "autocommit": False,
}
TELEGRAM_POSTER_TOKEN= os.environ.get("TELEGRAM_POSTER_TOKEN")