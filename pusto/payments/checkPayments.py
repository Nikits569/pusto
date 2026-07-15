from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from payments.bybit_client import get_recent_successful_deposits
from payments.models import Order
from payments.services import apply_promotion

# Допуск на сравнение сумм (защита от копеечных расхождений округления)
MATCH_TOLERANCE = Decimal("0.000001")


class Command(BaseCommand):
    help = "Сверяет последние депозиты Bybit с pending-заказами и помечает совпавшие как оплаченные"

    def handle(self, *args, **options):
        self._expire_stale_orders()

        # матчим депозиты только среди крипто-заказов — у Revolut/карты
        # своя ручная логика подтверждения через админку
        pending_orders = list(
            Order.objects.filter(
                status=Order.Status.PENDING,
                payment_method=Order.PaymentMethod.CRYPTO,
            )
        )
        if not pending_orders:
            return

        try:
            deposits = get_recent_successful_deposits(coin="USDT", limit=50)
        except Exception as exc:
            self.stderr.write(self.style.ERROR(f"Bybit API error: {exc}"))
            return

        for deposit in deposits:
            deposit_amount = Decimal(str(deposit["amount"]))
            tx_id = deposit.get("txID")

            # уже обработанные депозиты пропускаем (на случай если tx попал
            # в выборку повторно на следующем тике крона)
            if Order.objects.filter(tx_id=tx_id).exists():
                continue

            matched_order = next(
                (
                    o for o in pending_orders
                    if abs(deposit_amount - o.unique_amount) <= MATCH_TOLERANCE
                ),
                None,
            )

            if matched_order is None:
                continue

            matched_order.status = Order.Status.PAID
            matched_order.paid_at = timezone.now()
            matched_order.tx_id = tx_id
            matched_order.save(update_fields=["status", "paid_at", "tx_id"])

            apply_promotion(matched_order)

            pending_orders.remove(matched_order)
            self.stdout.write(
                self.style.SUCCESS(f"Order #{matched_order.id} → PAID (tx: {tx_id})")
            )

    def _expire_stale_orders(self):
        count = Order.objects.filter(
            status=Order.Status.PENDING,
            payment_method=Order.PaymentMethod.CRYPTO,
            expires_at__lt=timezone.now(),
        ).update(status=Order.Status.EXPIRED)

        if count:
            self.stdout.write(f"Помечено как истёкшие: {count}")