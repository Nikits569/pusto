from openai import OpenAI
from config_gpt import prompt, forbidden_texts
import os
import pymysql
import re
import json

from config import DB_CONFIG, secret_key

ALLOWED_FIELDS = {
    "categoria",
    "city",
    "productCategory",
    "price",
    "condition",
    "housingType",
    "rooms",
    "moveInDate",
    "deposit",
    "countNeighbors",
    "myGender",
    "neighborGender",
    "minAge",
    "maxAge",
}

client = OpenAI(api_key=secret_key[0])
total = 0
blocked = 0
gpt_processed = 0

def extract_rooms_regex(text: str):
    t = text.lower()

    # 1. Дробные "1.5", "2,5" — ПРОВЕРЯЕМ ПЕРВЫМ ДЕЛОМ.
    # Критично: если проверять паттерн "цифра+комн/izbov" раньше этого,
    # то для "2,5-izbov..." regex не находит совпадение на "2" (мешает запятая),
    # сдвигается вправо и матчит на хвостовой "5" перед "-izbov",
    # возвращая 5 вместо 2. Именно это и было причиной вашего бага.
    m = re.search(r'(\d+)[.,]5\b', t)
    if m:
        return int(m.group(1))

    # 2. Цифра + любой разделитель (дефис любого вида, точка, пробел) + "комн"/"кімн"/"izbov"/"izba"
    # Доп. защита: пропускаем совпадение, если найденная цифра сама является
    # дробным хвостом (стоит сразу после "." или "," и перед ними ещё цифра).
    for m in re.finditer(r'(\d+)[^\w\d]{0,3}(комн|кімн|izbov|izba)', t):
        start = m.start(1)
        if start >= 2 and t[start - 1] in '.,' and t[start - 2].isdigit():
            continue
        return int(m.group(1))

    # 3. Словесные числительные
    m = re.search(r'(одно|одна|дву[хс]?|трёх|трех|четырёх|четырех|пяти)\s*[-]?\s*(комнатн|комн)', t)
    if m:
        for key, val in {"одно": 1, "одна": 1, "дву": 2, "трёх": 3, "трех": 3, "четырёх": 4, "четырех": 4,
                         "пяти": 5}.items():
            if m.group(1).startswith(key):
                return val

    m = re.search(r'(jedno|dvoj|troj|štvor|pät)\s*izbov', t)
    if m:
        for key, val in {"jedno": 1, "dvoj": 2, "troj": 3, "štvor": 4, "pät": 5}.items():
            if m.group(1) == key:
                return val

    # 4. Студия/гарсонка — только если раньше НИЧЕГО не найдено
    if re.search(r'студи|garsón|garsonk|studio', t):
        return 1

    return None

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

def count_hits(text, keywords):
    text = text.lower()

    hits = 0

    for keyword in keywords:
        if re.search(rf"\b{re.escape(keyword.lower())}\b", text):
            hits += 1

    return hits

def get_matched_keywords(text: str, keywords: list[str]):
    text = text.lower()

    matched = []

    for keyword in keywords:
        if re.search(rf"\b{re.escape(keyword.lower())}\b", text):
            matched.append(keyword)

    return matched

def is_question(text):
    text = text.lower()

    #if "?" in text:
    #    return True

    for pattern in forbidden_texts["question_patterns"]:
        if pattern in text:
            return True

    return False

def contains_any(text, keywords):
    text = text.lower()

    for keyword in keywords:
        if keyword.lower() in text:
            return keyword

    return None

def pre_filter(text: str):

    hard_hit = contains_any(text, forbidden_texts["hard_block"])

    forbidden_hits = count_hits(
        text,
        forbidden_texts["forbidden_category"]
    )

    block_hits = count_hits(
        text,
        forbidden_texts["block_category"]
    )

    crypto_hits = count_hits(
        text,
        forbidden_texts["crypto"]
    )

    job_hits = count_hits(
        text,
        forbidden_texts["job"]
    )

    services_hits = count_hits(
        text,
        forbidden_texts["services"]
    )


    if hard_hit:
        return {
            "blocked": True,
            "reason": "hard_block",
            "keyword": hard_hit
        }
    if len(text.strip()) < 5:
        return {
            "blocked": True,
            "reason": "empty"
        }

    if is_question(text):
        return {
            "blocked": True,
            "reason": "question",
            "hits": 1
        }

    if forbidden_hits >= 1:
        return {
            "blocked": True,
            "reason": "forbidden_category",
            "hits": forbidden_hits
        }

    if block_hits >= 1:
        return {
            "blocked": True,
            "reason": "block_category",
            "hits": block_hits
        }

    if crypto_hits >= 1:
        return {
            "blocked": True,
            "reason": "crypto",
            "hits": crypto_hits
        }

    if job_hits >= 1:
        return {
            "blocked": True,
            "reason": "job",
            "hits": job_hits
        }

    if services_hits >= 1:
        return {
            "blocked": True,
            "reason": "services",
            "hits": services_hits
        }

    return {
        "blocked": False,
        "reason": None,
        "hits": 0
    }

def update_post(cursor, post_id, data):
    updates = []
    params = []


    for field, value in data.items():

        if field not in ALLOWED_FIELDS:
            continue

        if value is None:
            continue

        print('123')

        if isinstance(value, dict):

            if field == "price":
                min_price = value.get("min")
                max_price = value.get("max")

                if min_price is not None and max_price is not None:
                    value = f"{min_price}-{max_price}"
                elif min_price is not None:
                    value = str(min_price)
                elif max_price is not None:
                    value = str(max_price)
                else:
                    continue

            else:
                continue

        updates.append(f"`{field}` = %s")
        params.append(value)

    if updates:
        sql = f"""
            UPDATE base
            SET {', '.join(updates)}
            WHERE id = %s
        """

        params.append(post_id)
        cursor.execute(sql, params)


try:
    conn = pymysql.connect(**DB_CONFIG)
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT id, text
            FROM base
            WHERE id = 10090
            LIMIT 1
        """)

        results = cursor.fetchall()

        for row in results:

            print("=" * 80)
            print(row["id"])
            #print(row["text"])

            total += 1

            filter_result = pre_filter(row["text"])

            if filter_result["blocked"]:
                blocked += 1

                print(
                    f"POST BLOCKED: {filter_result['reason']}"
                )
                if filter_result["reason"] == "hard_block":
                    print(
                        f"HARD BLOCK: {filter_result['keyword']}"
                    )
                elif filter_result["reason"] == "question":
                    print("QUESTION DETECTED")

                elif filter_result["reason"] == "empty":
                    print("EMPTY POST")

                else:
                    print(
                        get_matched_keywords(
                            row["text"],
                            forbidden_texts[filter_result["reason"]]
                        )
                    )

                continue

            gpt_processed += 1

            try:
                data  = extract_ad_data(row["text"])

                print(data)

                update_post(
                    cursor,
                    row["id"],
                    data
                )
                conn.commit()
                print('UPDATE SUCCESS', row["id"])


            except Exception as e:

                print(f"ERROR ID={row['id']}: {e}")
                conn.commit()  # сохранить всё что уже обработано

                continue

            if total % 100 == 0:
                conn.commit()
                print(f"COMMIT {total}")
        conn.commit()
finally:
    conn.close()


