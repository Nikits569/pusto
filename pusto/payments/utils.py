import random
from decimal import Decimal

from .models import Order

# Диапазон "хвоста", который добавляем к сумме, чтобы отличать заказы
# 0.000001 .. 0.009999 USDT — незаметно для клиента, но уникально для матчинга
TAIL_MIN = 1
TAIL_MAX = 9999
TAIL_DIVISOR = Decimal(1_000_000)

MAX_ATTEMPTS = 20


def generate_unique_amount(base_amount: Decimal) -> Decimal:
    """
    Возвращает base_amount + случайный уникальный хвост,
    которого нет среди текущих pending-заказов.
    """
    for _ in range(MAX_ATTEMPTS):
        tail = Decimal(random.randint(TAIL_MIN, TAIL_MAX)) / TAIL_DIVISOR
        candidate = (base_amount + tail).quantize(Decimal("0.000001"))

        collision = Order.objects.filter(
            unique_amount=candidate,
            status=Order.Status.PENDING,
        ).exists()

        if not collision:
            return candidate

    raise RuntimeError(
        "Не удалось подобрать уникальную сумму — слишком много активных заказов одновременно"
    )