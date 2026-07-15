from decimal import Decimal

import requests
from django.core.cache import cache

FX_CACHE_KEY = "eur_usd_rate"
FX_CACHE_TTL_SECONDS = 300  # 5 минут — не дёргаем внешний API на каждый заказ


def get_eur_usd_rate() -> Decimal:
    """
    USDT привязан 1:1 к доллару США, поэтому курс EUR -> USDT
    практически равен курсу EUR -> USD.
    """
    cached = cache.get(FX_CACHE_KEY)
    if cached is not None:
        return Decimal(str(cached))

    response = requests.get(
        "https://api.frankfurter.app/latest",
        params={"from": "EUR", "to": "USD"},
        timeout=5,
    )
    response.raise_for_status()
    rate = Decimal(str(response.json()["rates"]["USD"]))

    cache.set(FX_CACHE_KEY, str(rate), FX_CACHE_TTL_SECONDS)
    return rate


def eur_to_usdt(amount_eur: Decimal) -> Decimal:
    rate = get_eur_usd_rate()
    return (amount_eur * rate).quantize(Decimal("0.01"))