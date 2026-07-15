from django.conf import settings
from pybit.unified_trading import HTTP

# Статус 3 у Bybit по документации/примерам соответствует успешно
# зачисленному депозиту. Перед продакшеном сверь актуальную таблицу
# статусов в официальной документации:
# https://bybit-exchange.github.io/docs/v5/asset/deposit/deposit-record
DEPOSIT_SUCCESS_STATUS = 3


def _get_session() -> HTTP:
    return HTTP(
        testnet=settings.BYBIT_TESTNET,  # False в проде
        api_key=settings.BYBIT_API_KEY,
        api_secret=settings.BYBIT_API_SECRET,
    )


def get_recent_successful_deposits(coin: str = "USDT", limit: int = 50) -> list[dict]:
    """
    Возвращает список успешно зачисленных депозитов по монете.
    Каждая запись содержит как минимум: coin, chain, amount, txID, status.
    """
    session = _get_session()
    response = session.get_deposit_records(coin=coin, limit=limit)

    if response.get("retCode") != 0:
        raise RuntimeError(f"Bybit API error: {response.get('retMsg')}")

    rows = response["result"]["rows"]
    return [row for row in rows if row.get("status") == DEPOSIT_SUCCESS_STATUS]