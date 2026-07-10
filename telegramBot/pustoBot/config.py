from dotenv import load_dotenv
import os
import pymysql

load_dotenv("../../.env")

DEBUG = bool(os.environ.get("DEBUG"))

TOKEN = os.environ.get("TELEGRAM_TOKEN")
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID")

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

TABLES = ["ads_thingspost", "ads_jobpost", "ads_neighborpost"]

TG_MIRROR = {
    "ads_thingspost": "products",
    "ads_jobpost": "jobs",
    "ads_neighborpost": "neighbors",
}

PROFILE_TABLE = "accounts_profile"
LINK_CODES_TABLE = "tg_link_codes"
POST_OWNER_FIELD = "user_id"