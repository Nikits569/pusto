# payments/admin.py
from django.contrib import admin, messages
from django.utils import timezone
from django.utils.html import format_html
from django.urls import reverse

import stripe
from django.conf import settings

from .models import TopPromotion, AdvPromotion, PendingAdvPromotion, StripeWebhookEvent

stripe.api_key = settings.STRIPE_SECRET_KEY


@admin.register(TopPromotion)
class TopPromotionAdmin(admin.ModelAdmin):
    list_display = (
        "id", "user", "target_link", "is_paid", "duration_days",
        "starts_at", "ends_at", "is_active", "payment_id", "created_at",
    )
    list_filter = ("is_paid", "content_type", "starts_at", "ends_at")
    search_fields = ("user__username", "user__email", "object_id", "payment_id")
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "starts_at", "ends_at", "payment_id")
    autocomplete_fields = ("user",)

    fieldsets = (
        (None, {"fields": ("user", "is_paid")}),
        ("Объект", {"fields": ("content_type", "object_id")}),
        ("Даты", {"fields": ("starts_at", "ends_at", "created_at")}),
        ("Платёж", {"fields": ("payment_id",)}),
    )

    def target_link(self, obj):
        if not getattr(obj, "target", None):
            return "-"
        return format_html(
            '<a href="/admin/{}/{}/{}/change/" target="_blank">{} #{}</a>',
            obj.content_type.app_label,
            obj.content_type.model,
            obj.object_id,
            obj.content_type.model,
            obj.object_id,
        )
    target_link.short_description = "Объект"

    def is_active(self, obj):
        return bool(obj.is_paid and obj.starts_at and obj.ends_at and obj.ends_at > timezone.now())
    is_active.boolean = True
    is_active.short_description = "Активно"


@admin.register(StripeWebhookEvent)
class StripeWebhookEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "event_type", "payment_intent_id", "status", "pending_id", "livemode")
    list_filter = ("event_type", "status", "livemode", "created_at")
    search_fields = ("event_id", "payment_intent_id")
    ordering = ("-created_at",)
    readonly_fields = (
        "event_id", "event_type", "payment_intent_id", "pending_id", "status",
        "amount", "amount_capturable", "livemode", "payload", "created_at",
    )


@admin.register(AdvPromotion)
class AdvPromotionAdmin(admin.ModelAdmin):
    list_display = (
        "id", "user", "ad_type", "status", "pay_state",
        "is_paid", "is_frozen", "duration_days",
        "starts_at", "ends_at",
        "last_intent_status", "created_at", "payment_id_short",
    )
    list_filter = ("status", "is_paid", "is_frozen", "ad_type", "created_at", "last_intent_status")
    search_fields = ("user__email", "user__username", "title", "payment_id")
    ordering = ("-created_at",)
    autocomplete_fields = ("user",)

    # Вариант B: разрешаем редактировать status, но не даём руками трогать флаги/даты
    readonly_fields = (
        "payment_id",
        "created_at",
        "last_webhook_event",
        "last_webhook_at",
        "last_intent_status",
        "is_paid",
        "is_frozen",
        "starts_at",
        "ends_at",
    )

    # Можно оставить только refresh/reject (approve не нужен в B)
    actions = ("action_reject_cancel", "action_refresh_from_stripe")

    fieldsets = (
        (None, {"fields": ("user", "title", "link", "image", "ad_type")}),
        ("Статус", {"fields": ("status", "duration_days", "is_paid", "is_frozen", "starts_at", "ends_at")}),
        ("Stripe", {"fields": ("payment_id", "last_intent_status", "last_webhook_event", "last_webhook_at")}),
        ("Служебное", {"fields": ("created_at",)}),
    )

    @admin.display(description="Pay state")
    def pay_state(self, obj: AdvPromotion):
        if obj.is_paid:
            return format_html('<b style="color:green;">PAID</b>')
        if obj.is_frozen or obj.last_intent_status == "requires_capture":
            return format_html('<b style="color:orange;">ON HOLD</b>')
        return format_html('<b style="color:#b00;">NOT PAID</b>')

    @admin.display(description="Payment ID")
    def payment_id_short(self, obj: AdvPromotion):
        return obj.payment_id[-10:] if obj.payment_id else "-"

    @admin.action(description="Reject (cancel) selected")
    def action_reject_cancel(self, request, queryset):
        ok = 0
        fail = 0

        for adv in queryset:
            if adv.status != AdvPromotion.Status.PENDING:
                fail += 1
                self.message_user(request, f"[{adv.id}] Skip: status != PENDING", level=messages.WARNING)
                continue

            try:
                intent = stripe.PaymentIntent.retrieve(adv.payment_id)
                if intent.status in ("requires_capture", "requires_action", "requires_confirmation", "requires_payment_method"):
                    stripe.PaymentIntent.cancel(adv.payment_id)

                adv.status = AdvPromotion.Status.REJECTED
                adv.is_paid = False
                adv.is_frozen = False
                adv.save(update_fields=["status", "is_paid", "is_frozen"])
                ok += 1

            except stripe.error.StripeError as e:
                fail += 1
                self.message_user(request, f"[{adv.id}] Stripe error: {e}", level=messages.ERROR)

        self.message_user(request, f"Reject done: ok={ok}, fail={fail}", level=messages.INFO)

    @admin.action(description="Refresh selected from Stripe (status only)")
    def action_refresh_from_stripe(self, request, queryset):
        ok = 0
        fail = 0
        now = timezone.now()

        for adv in queryset:
            try:
                intent = stripe.PaymentIntent.retrieve(adv.payment_id)
                adv.last_intent_status = intent.status
                adv.last_webhook_event = "admin.refresh"
                adv.last_webhook_at = now

                if intent.status == "requires_capture":
                    adv.is_frozen = True
                if intent.status == "succeeded":
                    adv.is_paid = True

                adv.save(update_fields=[
                    "last_intent_status", "last_webhook_event", "last_webhook_at",
                    "is_frozen", "is_paid"
                ])
                ok += 1
            except stripe.error.StripeError as e:
                fail += 1
                self.message_user(request, f"[{adv.id}] Stripe error: {e}", level=messages.ERROR)

        self.message_user(request, f"Refresh done: ok={ok}, fail={fail}", level=messages.INFO)


@admin.register(PendingAdvPromotion)
class PendingAdvPromotionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "ad_type", "duration_days", "checkout_key", "payment_intent_id",
                    "last_intent_status", "created_at", "debug_link")
    list_filter = ("ad_type", "duration_days", "created_at", "last_intent_status")
    search_fields = ("user__email", "checkout_key", "payment_intent_id")
    ordering = ("-created_at",)
    autocomplete_fields = ("user",)

    def debug_link(self, obj):
        try:
            url = reverse("stripe_debug_pending", args=[obj.id])
        except Exception:
            return "-"
        return format_html('<a href="{}" target="_blank">debug</a>', url)
    debug_link.short_description = "Stripe debug"