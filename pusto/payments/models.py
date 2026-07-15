from django.db import models
from django.utils import timezone
from django.conf import settings



class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Ожидает оплаты"
        PAID = "paid", "Оплачено"
        EXPIRED = "expired", "Истёк"

    class PaymentMethod(models.TextChoices):
        CRYPTO = "crypto", "Крипта (USDT)"
        REVOLUT = "revolut", "Revolut"
        CARD_UA = "card_ua", "Українська картка"

    class TypeOrder(models.TextChoices):

        UPGRADE = "up", "покращити оголошення"
        POST = "post", "рекламний пост"
        BANNER = "banner", "рекламний банер"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="orders", null=True, blank=True
    )
    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
        default=PaymentMethod.CRYPTO,
    )

    type_order = models.CharField(
        max_length=100,
        choices=TypeOrder.choices,
        default=TypeOrder.UPGRADE,
    )

    # заполняется только для ручных методов (Revolut / карта) —
    # телеграм-ник, телефон или email, чтобы с человеком связаться
    contact = models.CharField(max_length=150, blank=True, default="")

    # сумма, которую изначально хотел клиент (например 25.00) — актуально для крипты
    base_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    # base_amount + уникальный "хвост" (например 25.004821)
    # именно её показываем клиенту в QR и по ней матчим платёж — только для крипты
    unique_amount = models.DecimalField(
        max_digits=12, decimal_places=6, unique=True, null=True, blank=True
    )

    currency = models.CharField(max_length=10, default="USDT")
    chain = models.CharField(max_length=10, default="TRX")  # сеть TRC20

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)

    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    tx_id = models.CharField(max_length=120, null=True, blank=True)

    # --- то, что именно оплачивается: продвижение объявления ---
    # post_type: 'things' | 'job' | 'neighbor'
    post_type = models.CharField(max_length=20, null=True, blank=True)
    post_id = models.PositiveIntegerField(null=True, blank=True)
    duration_days = models.PositiveIntegerField(null=True, blank=True)
    price_eur = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    ad_image = models.ImageField(upload_to="ad_submissions/", null=True, blank=True)
    ad_text = models.TextField(null=True, blank=True)
    ad_link = models.URLField(null=True, blank=True)

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return self.status == self.Status.PENDING and timezone.now() > self.expires_at

    def __str__(self) -> str:
        label = self.unique_amount if self.unique_amount is not None else self.price_eur
        return f"Order #{self.id} ({label}, {self.get_payment_method_display()}) — {self.status}"