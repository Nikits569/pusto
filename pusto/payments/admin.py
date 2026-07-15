from django.contrib import admin
from django.utils import timezone

from .models import Order
from .services import apply_promotion


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "payment_method",
        "post_type",
        "type_order",
        "post_id",
        "price_eur",
        "contact",
        "status",
        "created_at",
        "paid_at",
    )
    list_filter = ("status", "payment_method")
    search_fields = ("id", "unique_amount", "tx_id", "contact", "post_id")
    ordering = ("-created_at",)
    actions = ["confirm_and_promote"]

    readonly_fields = (
        "payment_method",
        "contact",
        "base_amount",
        "unique_amount",
        "currency",
        "chain",
        "post_type",
        "type_order",
        "post_id",
        "duration_days",
        "price_eur",
        "created_at",
        "paid_at",
        "tx_id",
        "ad_image",
        "ad_text",
        'ad_link',
    )

    # Заказы создаются только через сайт (кнопка "підняти"), не руками
    def has_add_permission(self, request):
        return False

    def get_fields(self, request, obj=None):
        return [
            "payment_method",
            "contact",
            "post_type",
            "type_order",
            "post_id",
            "duration_days",
            "price_eur",
            "base_amount",
            "unique_amount",
            "currency",
            "chain",
            "status",
            "tx_id",
            "created_at",
            "paid_at",
            "expires_at",
            "ad_image",
            "ad_text",
            'ad_link',
        ]

    @admin.action(description="Подтвердить оплату и поднять объявление")
    def confirm_and_promote(self, request, queryset):
        confirmed = 0
        for order in queryset:
            if order.status == Order.Status.PAID:
                continue  # уже подтверждён — пропускаем, чтобы не сдвигать promoted_until повторно

            order.status = Order.Status.PAID
            order.paid_at = timezone.now()
            order.save(update_fields=["status", "paid_at"])

            if apply_promotion(order):
                confirmed += 1

        self.message_user(request, f"Подтверждено и поднято объявлений: {confirmed}")