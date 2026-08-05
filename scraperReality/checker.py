import pymysql
import re
import requests
import os
from config import DB_CONFIG
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "sk-SK,sk;q=0.9,en;q=0.8",
}

conn = pymysql.connect(**DB_CONFIG)
session = requests.Session()

try:
    with conn.cursor() as cursor:
        cursor.execute("""
        SELECT source_url FROM reality
        """)
        for i in cursor.fetchall():
            source_url = i["source_url"]

            resp = session.get(source_url, headers=HEADERS, timeout=20)
            resp.raise_for_status()

            if resp.url != source_url:
                print(f"Удалено: {source_url}")

                cursor.execute(
                    "DELETE FROM reality WHERE source_url = %s",
                    (source_url,)
                )

                cursor.execute(
                    "DELETE FROM ads_neighborpost WHERE link_bazos = %s",
                    (source_url,)
                )

                conn.commit()

                print(
                    f"Удалено из reality: {cursor.rowcount}"
                )

            else:
                print(f"OK: {source_url}")

except Exception as e:
    print(e)

finally:
    conn.close()
