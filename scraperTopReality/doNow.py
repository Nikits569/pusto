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
        SELECT source_url, topreality_id FROM topreality
        """)
        for i in cursor.fetchall():
            resp = session.get(i['source_url'], headers=HEADERS, timeout=20)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")

            for li in soup.select("li.list-group-item"):
                span = li.find("span")
                if span and span.get_text(strip=True) == "Ulica":



                    street = li.find("strong").get_text(strip=True)
                    print('Update', i['topreality_id'], street)

                    cursor.execute("""
                        UPDATE topreality
                        SET adress = %s
                        WHERE topreality_id = %s
                    """, (street, i["topreality_id"]))

                    conn.commit()
                    break

except Exception as e:
    print(e)

finally:
    conn.close()
