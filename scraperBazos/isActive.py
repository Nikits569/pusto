"""
Проверка объявлений bazos по source_url из таблицы `bazos`.
Если объявление не существует (не открывается / редирект / 404) —
СРАЗУ (в том же проходе) удаляем строку из `bazos` и связанную строку:
  - если category = 'reality'  -> из `ads_neighborpost`
  - иначе                       -> из `ads_thingspost`
(в обеих: source = 'bazos', link_bazos = source_url)

Никакого отдельного "сначала проверить всё, потом удалить" — проверили
одну строку, если мёртвая, тут же удалили и закоммитили, тут же
напечатали id. Так результат видно сразу, а не через часы после того,
как скрипт пройдёт всю таблицу.

Логика проверки "существует / не существует":
1. GET-запрос с allow_redirects=True.
2. Если после редиректов path отличается от исходного -> нет объявления.
3. Код ответа не 200 -> нет объявления.
4. Маркеры "объявление не найдено" в тексте страницы (см. MARKERS,
   это заглушка, подставь реальные фразы если нужно).
"""

import time
from urllib.parse import urlparse

import pymysql
import requests

from config import DB_CONFIG

# ---- настройки ----
TIMEOUT = 10
DELAY_BETWEEN = 1.0
DRY_RUN = False   # True = только печатать что удалили бы, без реального DELETE

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

MARKERS = [
    "inzerát neexistuje",
    "inzerát bol zmazaný",
    "stránka nenájdená",
    "nebola nájdená",
]


def check_url_exists(url: str):
    try:
        resp = requests.get(
            url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True
        )
    except requests.RequestException as e:
        return False, f"ошибка запроса: {e}"

    original_path = urlparse(url).path.rstrip("/")
    final_path = urlparse(resp.url).path.rstrip("/")

    if resp.history and final_path != original_path:
        return False, f"редирект: {resp.url}"

    if resp.status_code != 200:
        return False, f"код ответа {resp.status_code}"

    lower_text = resp.text.lower()
    for marker in MARKERS:
        if marker.lower() in lower_text:
            return False, f"найден маркер отсутствия объявления: '{marker}'"

    return True, "OK"


def target_table_for(category: str) -> str:
    if (category or "").strip().lower() == "reality":
        return "ads_neighborpost"
    return "ads_thingspost"


def delete_dead_ad(conn, row_id: int, url: str, category: str):
    """
    Удаляет строку из bazos (по id) и связанную строку из нужной таблицы.
    Commit сразу. Возвращает (table_name, bazos_deleted, other_deleted).
    """
    table = target_table_for(category)

    with conn.cursor() as cursor:
        if url:
            cursor.execute(
                f"""
                DELETE FROM {table}
                WHERE source = 'bazos' AND link_bazos = %s
                """,
                (url,),
            )
            other_deleted = cursor.rowcount
        else:
            other_deleted = 0

        cursor.execute("DELETE FROM bazos WHERE id = %s", (row_id,))
        bazos_deleted = cursor.rowcount

    conn.commit()
    return table, bazos_deleted, other_deleted


def main():
    conn = pymysql.connect(**DB_CONFIG)

    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(
                """
                SELECT id, source_url, category
                FROM bazos
                ORDER BY RAND()
                """
            )
            rows = cursor.fetchall()

        print(f"Найдено строк для проверки: {len(rows)}\n")
        if DRY_RUN:
            print(">>> DRY_RUN = True: реального удаления НЕ будет <<<\n")

        checked = 0
        deleted = 0

        for row in rows:
            row_id = row["id"]
            url = row["source_url"]
            category = row.get("category")
            checked += 1

            if not url:
                print(f"{row_id} | (пустой source_url) -> НЕ СУЩЕСТВУЕТ (нет URL)")
                exists = False
                reason = "нет URL"
            else:
                exists, reason = check_url_exists(url)
                status = "СУЩЕСТВУЕТ" if exists else "НЕ СУЩЕСТВУЕТ"
                print(f"{row_id} | {url} -> {status} ({reason})")

            if not exists:
                if DRY_RUN:
                    table = target_table_for(category)
                    print(f"    [DRY_RUN] удалили бы id={row_id} из bazos и из {table}")
                else:
                    table, bazos_deleted, other_deleted = delete_dead_ad(
                        conn, row_id, url, category
                    )
                    print(
                        f"    >>> УДАЛЕНО id={row_id} category={category!r} "
                        f"из bazos={bazos_deleted}, из {table}={other_deleted}"
                    )
                    deleted += 1

            if url:
                time.sleep(DELAY_BETWEEN)

        print(f"\nГотово. Проверено: {checked}, удалено: {deleted}")

    finally:
        conn.close()


if __name__ == "__main__":
    main()