#!/usr/bin/env python3
"""
Тестирует список Django-эндпоинтов на реальном сервере.
Использование:
    python test_endpoints.py https://your-domain.com endpoints.txt

Что делает:
  - Подставляет тестовые значения вместо <slug:slug>, <int:pk>, <uuid:token> и т.д.
  - Пропускает "опасные" пути (admin add/delete/change/history, regex-заглушки, media)
  - Делает GET-запрос по каждому пути
  - Логирует статус, время ответа
  - Отдельно подсвечивает 5xx (баги на сервере) — по ним стоит сразу смотреть логи Django
  - 404 и 3xx помечает предупреждением (может быть ожидаемо: несуществующий slug/id, редирект на логин)
  - В конце пишет errors.log с полным списком проблемных URL и подробностями ответа
"""

import sys
import re
import time
import requests

# ---------- Тестовые значения для параметров пути ----------
# Подставь сюда РЕАЛЬНЫЕ существующие значения из своей БД, чтобы проверка
# страниц типа /things/<slug>/ была осмысленной, а не просто ловила 404.
PARAM_VALUES = {
    "slug": "test-slug",
    "pk": "1",
    "id": "1",
    "idProfile": "1",
    "object_id": "1",
    "post_id": "1",
    "order_id": "1",
    "title": "test-title",
    "section": "things",
    "ad_type": "thing",
    "post_type": "thing",
    "app_label": "ads",
    "model_name": "thingspost",
    "token": "invalid-token-for-test",
    "uuid": "00000000-0000-0000-0000-000000000000",
    "path": "1",
    "content_type_id": "1",
}

# Паттерны путей, которые пропускаем полностью (не имеет смысла/опасно GET-ить)
SKIP_SUBSTRINGS = [
    "/add/",
    "/delete/",
    "/change/",
    "/history/",
    "^(?P",          # regex-заглушки типа ^(?P<app_label>...)$
    "(?P<url>",      # catch-all админки
    "^media/",       # обслуживается веб-сервером, не Django view
    "<path:object_id>",  # detail-страницы объектов админки без реального ID
    "<path:content_type_id>",
]


def fill_params(path: str) -> str | None:
    """Заменяет <type:name> на тестовое значение. Возвращает None, если не знаем чем заполнить."""

    def repl(match):
        full = match.group(1)  # например "slug:slug" или "int:pk"
        if ":" in full:
            _, name = full.split(":", 1)
        else:
            name = full
        if name in PARAM_VALUES:
            return PARAM_VALUES[name]
        return None  # сигнал, что не нашли значение

    pattern = re.compile(r"<([^>]+)>")
    missing = []

    def repl_track(match):
        val = repl(match)
        if val is None:
            missing.append(match.group(0))
            return match.group(0)
        return val

    result = pattern.sub(repl_track, path)
    if missing:
        return None
    return result


def should_skip(path: str) -> bool:
    return any(s in path for s in SKIP_SUBSTRINGS)


def main():
    if len(sys.argv) < 3:
        print("Использование: python test_endpoints.py <base_url> <endpoints_file>")
        print("Пример: python test_endpoints.py https://example.com endpoints.txt")
        sys.exit(1)

    base_url = sys.argv[1].rstrip("/")
    endpoints_file = sys.argv[2]

    with open(endpoints_file, encoding="utf-8") as f:
        raw_paths = [line.strip() for line in f if line.strip()]

    session = requests.Session()
    session.headers.update({"User-Agent": "EndpointHealthCheck/1.0"})

    results = []
    skipped = []
    unresolved = []

    for path in raw_paths:
        if should_skip(path):
            skipped.append(path)
            continue

        resolved = fill_params(path)
        if resolved is None:
            unresolved.append(path)
            continue

        url = f"{base_url}/{resolved.lstrip('/')}"

        try:
            start = time.time()
            resp = session.get(url, timeout=15, allow_redirects=True)
            elapsed = time.time() - start
            status = resp.status_code

            if status >= 500:
                marker = "❌"
            elif status >= 400:
                marker = "⚠️ "
            elif 300 <= status < 400:
                marker = "↪️ "
            else:
                marker = "✅"

            print(f"{marker} {status} | {elapsed:5.2f}s | {url}")
            results.append({
                "url": url,
                "status": status,
                "elapsed": elapsed,
                "final_url": resp.url,
                "body_snippet": resp.text[:300] if status >= 500 else "",
            })

        except requests.exceptions.RequestException as e:
            print(f"❌ ERROR   | {url} | {e}")
            results.append({"url": url, "status": "ERROR", "elapsed": None, "final_url": "", "body_snippet": str(e)})

    # ---------- Сводка ----------
    print("\n" + "=" * 60)
    print("ИТОГ")
    print("=" * 60)
    print(f"Проверено:           {len(results)}")
    print(f"Пропущено (admin/regex/media): {len(skipped)}")
    print(f"Пропущено (нет значения параметра): {len(unresolved)}")

    server_errors = [r for r in results if r["status"] == "ERROR" or (isinstance(r["status"], int) and r["status"] >= 500)]
    client_errors = [r for r in results if isinstance(r["status"], int) and 400 <= r["status"] < 500]
    redirects = [r for r in results if isinstance(r["status"], int) and 300 <= r["status"] < 400]

    print(f"\n❌ Серверных ошибок (5xx/ERROR): {len(server_errors)}")
    for r in server_errors:
        print(f"   {r['status']} -> {r['url']}")

    print(f"\n⚠️  Клиентских ошибок (4xx): {len(client_errors)}")
    for r in client_errors:
        print(f"   {r['status']} -> {r['url']}")

    print(f"\n↪️  Редиректов (3xx, часто норм — логин/языковой префикс): {len(redirects)}")
    for r in redirects:
        print(f"   {r['status']} -> {r['url']} -> {r['final_url']}")

    if unresolved:
        print(f"\nℹ️  Эти пути пропущены — впиши для них реальные тестовые значения в PARAM_VALUES и перезапусти:")
        for p in unresolved:
            print(f"   {p}")

    # ---------- Подробный лог ошибок в файл ----------
    if server_errors:
        with open("errors.log", "w", encoding="utf-8") as f:
            for r in server_errors:
                f.write(f"URL: {r['url']}\nSTATUS: {r['status']}\nBODY SNIPPET:\n{r['body_snippet']}\n{'-'*60}\n")
        print(f"\n📄 Подробности серверных ошибок записаны в errors.log")


if __name__ == "__main__":
    main()