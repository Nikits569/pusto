import os
from pathlib import Path
from dotenv import load_dotenv
import pymysql

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / "../../../.env")

DB_CONFIG = {
    "host": os.environ.get("DB_HOST"),
    "port": int(os.environ.get("DB_PORT", 3306)),
    "user": os.environ.get("DB_USER"),
    "password": os.environ.get("DB_PASSWORD"),
    "database": os.environ.get("DB_NAME"),
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
    "autocommit": False,
}

api_id = os.environ.get("TG_API_ID")
api_hash = os.environ.get("TG_API_HASH")
SESSION = '/var/www/app/pusto/postWorker/PostTaker/postChecker/checker'

