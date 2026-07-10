import json
import re
from openai import OpenAI
from config import secret_key, DB_CONFIG
import pymysql

client = OpenAI(api_key=secret_key)

# ---------- ЭТАП 1: REGEX (приоритетный, детерминированный) ----------

WORD_NUMBERS = {
    "одно": 1, "одна": 1, "1-": 1, "перв": 1,
    "дву": 2, "двух": 2, "второ": 2, "dvoj": 2,
    "трёх": 3, "трех": 3, "трой": 3, "troj": 3,
    "четырёх": 4, "четырех": 4, "štvor": 4,
    "пяти": 5, "pät": 5,
}

def extract_rooms_regex(text: str):
    t = text.lower()
    # 1. Цифра + любой разделитель (дефис любого вида, точка, пробел) + "комн"/"izbov"/"izba"
    m = re.search(r'(\d+)[^\w\d]{0,3}(комн|izbov|izba)', t)
    if m:
        return int(m.group(1))

    # 2. Дробные "1.5", "2,5"
    m = re.search(r'(\d+)[.,]5\b', t)
    if m:
        return int(m.group(1))

    # 3. Словесные числительные
    m = re.search(r'(одно|одна|дву[хс]?|трёх|трех|четырёх|четырех|пяти)\s*[-]?\s*(комнатн|комн)', t)
    if m:
        for key, val in {"одно":1,"одна":1,"дву":2,"трёх":3,"трех":3,"четырёх":4,"четырех":4,"пяти":5}.items():
            if m.group(1).startswith(key):
                return val

    m = re.search(r'(jedno|dvoj|troj|štvor|pät)\s*izbov', t)
    if m:
        for key, val in {"jedno":1,"dvoj":2,"troj":3,"štvor":4,"pät":5}.items():
            if m.group(1) == key:
                return val

    # 4. Студия/гарсонка — только если раньше НИЧЕГО не найдено
    if re.search(r'студи|garsón|garsonk|studio', t):
        return 1

    return None


# ---------- ЭТАП 2: GPT (fallback, только если regex не справился) ----------

prompt = """
Ты работаешь как интеллектуальный классификатор объявлений платформы pusto.sk.
Объявления могут быть на словацком, английском, украинском или русском языке.

Твоя задача — определить количество комнат и адрес.

Правила по комнатам (применяй строго по порядку):
1. Если есть число рядом с "комн"/"izbov" — это и есть количество комнат, ИГНОРИРУЙ любые другие слова рядом (включая "студия").
   Пример: "2-комн. студия" → rooms = 2
2. Дробные (1.5, 2,5) — целая часть.
3. "студия"/"garsónka" без числа рядом — rooms = 1.
4. Если ничего не подходит — rooms = null.

Правила по адресу:
Если адрес точно не написан — не угадывай, ставь null.

Примеры адресов:
Martina Granca, Dúbravka
Horský park – Havlíčkova, Staré Mesto
Старый город, ул. Chorvátska
Петржалка, ул. Krasovského

Верни строго JSON без markdown:
{
"rooms": null,
"adress": null
}
"""

def extract_with_gpt(text: str):
    response = client.responses.create(
        model="gpt-4.1-mini",
        input=f"{prompt}\n\nОбъявление:\n{text}",
        temperature=0,
    )
    return json.loads(response.output_text)


# ---------- ГИБРИДНАЯ ЛОГИКА ----------

def extract_ad_data(text: str):
    rooms_regex = extract_rooms_regex(text)
    gpt_data = extract_with_gpt(text)  # GPT нужен в любом случае — за адресом

    if rooms_regex is not None:
        gpt_data['rooms'] = rooms_regex
        gpt_data['rooms_source'] = 'regex'
    else:
        gpt_data['rooms_source'] = 'gpt'

    return gpt_data


try:
    conn = pymysql.connect(**DB_CONFIG)
    with conn.cursor() as cursor:
        cursor.execute("SELECT id, text FROM ads_neighborpost WHERE source = 'telegram';")
        info = cursor.fetchall()
        for i in info:
            data = extract_ad_data(i['text'])
            print(data)
            cursor.execute("UPDATE ads_neighborpost SET rooms=%s, adress=%s WHERE id=%s;",(data['rooms'], data['adress'], i['id']))
            conn.commit()
            print('FINISH COMMIT', i['id'])

finally:
    conn.close()