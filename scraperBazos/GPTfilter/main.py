from openai import OpenAI
from config_gpt import prompt
import os
import pymysql
import json
import re
from config import DB_CONFIG, secret_key

client = OpenAI(api_key=secret_key[0])

PATTERNS = [

    # Ulica: Pionierska
    r'(?i)\bulica\s*:\s*([^\n\r,.;]+)',

    # Obec: Prešov
    r'(?i)\bobec\s*:\s*([^\n\r,.;]+)',

    # Mestská časť: Sihoť III
    r'(?i)\bmestská\s+časť\s*:\s*([^\n\r,.;]+)',

    # sídlisko Sekčov
    r'(?i)\bsídlisko\s+([A-Za-zÁÄČĎÉÍĹĽŇÓÔŔŠŤÚÝŽáäčďéíĺľňóôŕšťúýž0-9 ]{2,40})',

    # časť Ružinov
    r'(?i)\bčasť\s+([A-Za-zÁÄČĎÉÍĹĽŇÓÔŔŠŤÚÝŽáäčďéíĺľňóôŕšťúýž0-9 ]{2,40})',

    # na ulici Slovenského odboja
    r'(?i)\bna\s+ulici\s+([A-Za-zÁÄČĎÉÍĹĽŇÓÔŔŠŤÚÝŽáäčďéíĺľňóôŕšťúýž0-9.\- ]{2,40})',

    # na Kukučínovej ulici
    r'(?i)\bna\s+([A-Za-zÁÄČĎÉÍĹĽŇÓÔŔŠŤÚÝŽáäčďéíĺľňóôŕšťúýž0-9.\- ]{2,40})\s+ulici',

    # ul. Mládeže
    r'(?i)\bul\.?\s*([A-Za-zÁÄČĎÉÍĹĽŇÓÔŔŠŤÚÝŽáäčďéíĺľňóôŕšťúýž0-9.\- ]{2,40})',

    # Vajanského, Budovateľská...
    r'\b([A-ZÁÄČĎÉÍĹĽŇÓÔŔŠŤÚÝŽ][A-Za-zÁÄČĎÉÍĹĽŇÓÔŔŠŤÚÝŽáäčďéíĺľňóôŕšťúýž.\-]+(?:ská|skej|ského|ovej|ného|ého|ej|kej))\b',

    # Nový Smokovec
    r'\b([A-ZÁÄČĎÉÍĹĽŇÓÔŔŠŤÚÝŽ][a-záäčďéíĺľňóôŕšťúýž]+\s+[A-ZÁÄČĎÉÍĹĽŇÓÔŔŠŤÚÝŽ][a-záäčďéíĺľňóôŕšťúýž]+)\b',
]

BLACKLIST = {

    "ponúkame",
    "ponúkam",
    "prenájom",
    "byt",
    "vybavenie",
    "balkón",
    "pivnica",
    "centrum",
    "reality",
    "výmera",
    "rozloha",
    "cena",
    "voľný",
    "kompletne",
    "zariadený",
    "novostavba",
    "obývačka",
    "spálňa",
    "kuchyňa",
    "kúpeľňa",
    "chodba",
    "parkovanie",

    # мусор
    "property",
    "delta",
    "real",
    "popis",
    "reklamy",
    "kontajnery",
    "vozíme",
    "vlastnými",
    "hľadáte",
    "inzeráty",
    "palace",
    "hill",
    "rezidencia",
}

BAD_EXACT = {

    "ica",
    "ici",
    "ul",
    "ul.",
    "ulica",
    "obec",
    "časť",
    "nám",
    "obr",
    "pri",
    "starého",
    "malého",
}


def clean_location(location: str):

    location = location.strip()

    # убрать "v Prešove", "v Sabinove"
    location = re.sub(r"\sv\s+[A-ZÁÄČĎÉÍĹĽŇÓÔŔŠŤÚÝŽ].*$", "", location)

    # убрать всё после цифры
    location = re.split(r"\d", location)[0]

    # убрать после точки, запятой, скобки
    location = re.split(r"[.,;()]", location)[0]

    # убрать "o výmere"
    location = re.split(r"\so\s", location, flags=re.I)[0]

    location = re.sub(r"\s+", " ", location).strip()

    if location.endswith(" č"):
        location = location[:-2].strip()

    return location


def is_valid(location: str):

    if not location:
        return False

    if len(location) < 3:
        return False

    if len(location.split()) > 3:
        return False

    low = location.lower()

    if low in BAD_EXACT:
        return False

    if low.startswith(("ica", "ici")):
        return False

    if any(word in low for word in BLACKLIST):
        return False

    if "(" in location or ")" in location:
        return False

    return True

def extract_with_gpt(text: str):
    response = client.responses.create(
        model="gpt-4.1-mini",
        input=f"{prompt}\n\nОбъявление:\n{text}",
        temperature=0,
    )

    content = response.output_text.strip()

    content = re.sub(r"^```json\s*", "", content)
    content = re.sub(r"\s*```$", "", content)

    return json.loads(content)

def extract_location(text: str):

    if not text:
        return None

    for pattern in PATTERNS:

        match = re.search(pattern, text)

        if not match:
            continue

        location = clean_location(match.group(1))

        if is_valid(location):
            return location

    return None

try:
    conn = pymysql.connect(**DB_CONFIG)

    with conn.cursor() as cursor:
        print("start")

        cursor.execute("SELECT text_sk, bazos_id FROM bazos WHERE type = 'rent' AND adress IS NULL")

        for row in cursor.fetchall():
            address = extract_location(row["text_sk"])

            cursor.execute(
                """
                UPDATE bazos
                SET adress = %s
                WHERE bazos_id = %s
                """,
                (address, row["bazos_id"])
            )

            print(address)
            conn.commit()

        print("start AI filters")

        cursor.execute("""
            SELECT text_sk, bazos_id
            FROM bazos
            WHERE type = 'rent'
              AND adress IS NULL
        """)

        for row in cursor.fetchall():

            result = extract_with_gpt(row["text_sk"])

            address = result.get("adress")

            # Строгий маркер, если адрес не найден
            if not address:
                address = "__NO_ADDRESS__"

            cursor.execute(
                """
                UPDATE bazos
                SET adress = %s
                WHERE bazos_id = %s
                """,
                (address, row["bazos_id"])
            )

            print(f"UPDATE {row['bazos_id']} -> {address}")

            conn.commit()

except Exception as e:
    print(e)

finally:
    conn.close()
