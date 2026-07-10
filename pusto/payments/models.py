from django.db import models
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
import uuid


class TopPromotion(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="top_promotions",
        verbose_name=_("User")
    )

    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        limit_choices_to=models.Q(app_label='ads', model__in=['jobpost', 'thingspost', 'neighborpost']),
        verbose_name=_("Content type")
    )
    object_id = models.PositiveIntegerField(verbose_name=_("Object ID"))
    target = GenericForeignKey("content_type", "object_id")

    duration_days = models.PositiveSmallIntegerField(default=7, verbose_name=_("Duration (days)"))
    starts_at = models.DateTimeField(blank=True, null=True, verbose_name=_("Starts at"))
    ends_at = models.DateTimeField(blank=True, null=True, verbose_name=_("Ends at"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created at"))

    payment_id = models.CharField(max_length=255, blank=True, null=True, unique=True, verbose_name=_("Payment ID"))
    is_paid = models.BooleanField(default=False, verbose_name=_("Is paid"))
    is_active = models.BooleanField(default=True, verbose_name=_("Is active"))

    class Meta:
        indexes = [
            models.Index(fields=["content_type_id", "object_id"]),
        ]
        ordering = ["-created_at"]
        verbose_name = _("Top promotion")
        verbose_name_plural = _("Top promotions")

    def __str__(self):
        return f"TopPromotion #{self.pk} → {self.target}"

    def mark_paid(self):
        if not self.is_paid:
            self.is_paid = True
            self.save(update_fields=["is_paid"])


class PendingAdvPromotion(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name=_("User")
    )
    title = models.CharField(max_length=255, verbose_name=_("Title"))
    link = models.URLField(blank=True, null=True, verbose_name=_("Link"))
    image = models.ImageField(upload_to="ads/", null=True, blank=True, verbose_name=_("Image"))
    ad_type = models.CharField(max_length=50, verbose_name=_("Ad type"))
    payment_intent_id = models.CharField(max_length=255, unique=True, verbose_name=_("Payment intent ID"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created at"))
    checkout_key = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, verbose_name=_("Checkout key"))
    duration_days = models.PositiveIntegerField(default=3, verbose_name=_("Duration (days)"))

    is_refunded = models.BooleanField(default=False, verbose_name=_("Is refunded"))
    refund_id = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("Refund ID"))

    last_webhook_event = models.CharField(max_length=120, blank=True, null=True, verbose_name=_("Last webhook event"))
    last_webhook_at = models.DateTimeField(blank=True, null=True, verbose_name=_("Last webhook at"))
    last_intent_status = models.CharField(max_length=64, blank=True, null=True, verbose_name=_("Last intent status"))

    class Meta:
        verbose_name = _("Pending promotion")
        verbose_name_plural = _("Pending promotions")


class AdvPromotion(models.Model):

    class Status(models.TextChoices):
        PENDING = "PENDING", _("Pending")
        ACTIVE = "ACTIVE", _("Active")
        REJECTED = "REJECTED", _("Rejected")

    title = models.CharField(max_length=255, verbose_name=_("Title"))
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name=_("User")
    )
    link = models.URLField(blank=True, null=True, verbose_name=_("Link"))
    image = models.ImageField(upload_to="ads/", null=True, blank=True, verbose_name=_("Image"))
    ad_type = models.CharField(max_length=50, verbose_name=_("Ad type"))
    payment_id = models.CharField(max_length=255, unique=True, verbose_name=_("Payment ID"))
    is_paid = models.BooleanField(default=False, verbose_name=_("Is paid"))
    is_frozen = models.BooleanField(default=False, verbose_name=_("Is frozen"))
    starts_at = models.DateTimeField(blank=True, null=True, verbose_name=_("Starts at"))
    ends_at = models.DateTimeField(blank=True, null=True, verbose_name=_("Ends at"))
    duration_days = models.PositiveIntegerField(default=7, verbose_name=_("Duration (days)"))

    last_webhook_event = models.CharField(max_length=120, blank=True, null=True, verbose_name=_("Last webhook event"))
    last_webhook_at = models.DateTimeField(blank=True, null=True, verbose_name=_("Last webhook at"))
    last_intent_status = models.CharField(max_length=64, blank=True, null=True, verbose_name=_("Last intent status"))

    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name=_("Status")
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created at"))

    class Meta:
        verbose_name = _("Advertisement promotion")
        verbose_name_plural = _("Advertisement promotions")


class StripeWebhookEvent(models.Model):
    event_id = models.CharField(max_length=255, unique=True, verbose_name=_("Event ID"))
    event_type = models.CharField(max_length=120, verbose_name=_("Event type"))
    payment_intent_id = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("Payment intent ID"))
    pending_id = models.BigIntegerField(blank=True, null=True, verbose_name=_("Pending ID"))

    status = models.CharField(max_length=64, blank=True, null=True, verbose_name=_("Status"))
    amount = models.BigIntegerField(blank=True, null=True, verbose_name=_("Amount"))
    amount_capturable = models.BigIntegerField(blank=True, null=True, verbose_name=_("Capturable amount"))
    livemode = models.BooleanField(default=False, verbose_name=_("Live mode"))

    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created at"))

    payload = models.JSONField(blank=True, null=True, verbose_name=_("Payload"))

    def __str__(self):
        return f"{self.event_type} ({self.event_id})"