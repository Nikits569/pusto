"""
Единая точка чтения цен на тарифы из pricing.json.

Файл pricing.json должен лежать рядом с этим модулем:
    payments/
        pricing.py       <- этот файл
        pricing.json      <- сюда меняешь цены, без деплоя кода

ВАЖНО: цены отсюда — единственный источник правды. Фронт присылает
price_eur только для UX (показать пользователю), но сервер всегда
проверяет его через get_price() перед созданием Order. Иначе через
devtools можно подменить цену на 0.01 €.
"""
import json
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Optional

PRICING_FILE = Path(__file__).resolve().parent / "pricing.json"


@lru_cache(maxsize=1)
def _load_pricing() -> dict:
    with open(PRICING_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def reload_pricing() -> None:
    """
    Сбросить кэш цен. lru_cache держит pricing.json в памяти процесса,
    поэтому если правишь JSON без рестарта Django (например, через
    management-команду или сигнал файловой системы) — вызови это.
    При обычном деплое с рестартом процесса вызывать не обязательно.
    """
    _load_pricing.cache_clear()


def get_price(type_order: str, duration_days: int) -> Optional[Decimal]:
    """
    Вернуть цену в EUR для (type_order, duration_days) из pricing.json,
    либо None если такой комбинации нет — это сигнал, что фронт прислал
    что-то не соответствующее актуальному прайсу (например, устаревший
    закешированный тариф).
    """
    data = _load_pricing()
    tariff = data.get(type_order, {})
    raw = tariff.get(str(duration_days))
    return Decimal(str(raw)) if raw is not None else None


def get_all_tariffs() -> dict:
    """
    Для рендера тайлов в шаблонах. Возвращает:
    {
        "up": [{"duration_days": 3, "price_eur": Decimal("2.99")}, ...],
        "post": [...],
        "banner": [...],
    }
    Отсортировано по возрастанию duration_days.
    """
    data = _load_pricing()
    return {
        type_order: [
            {"duration_days": int(days), "price_eur": Decimal(str(price))}
            for days, price in sorted(tariffs.items(), key=lambda kv: int(kv[0]))
        ]
        for type_order, tariffs in data.items()
    }