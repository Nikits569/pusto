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
        SELECT source_url, reality_id FROM reality
        """)
        for i in cursor.fetchall():
            address = None

            resp = session.get(i['source_url'], headers=HEADERS, timeout=20)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")

            location = soup.find("div", class_="d-inline-block ml-2")

            if location:
                a = location.find("a")
                if a:
                    a.decompose()

                address = location.get_text(" ", strip=True)
                address = address.split("•")[0].strip()

            if not address:
                print(f"Не найден адрес: {i['source_url']}")
                continue

            print("Update", i["reality_id"], address)

            cursor.execute("""
                UPDATE reality
                SET adress = %s
                WHERE reality_id = %s
            """, (address, i["reality_id"]))

            print(cursor.rowcount)
            conn.commit()


except Exception as e:
    print(e)

finally:
    conn.close()
