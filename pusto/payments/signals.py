# payments/signals.py
import stripe
from django.conf import settings
from django.db.models.signals import pre_save
from django.dispatch import receiver

from .models import AdvPromotion

stripe.api_key = settings.STRIPE_SECRET_KEY


@receiver(pre_save, sender=AdvPromotion)
def capture_on_admin_activate(sender, instance: AdvPromotion, **kwargs):
    """
    Вариант B:
    - если админ меняет статус PENDING -> ACTIVE
      и есть холд (is_frozen=True) + PI requires_capture
      то делаем capture().
    - is_paid/is_frozen и финальный ACTIVE выставит webhook на payment_intent.succeeded.
    """
    if not instance.pk:
        return

    old = AdvPromotion.objects.filter(pk=instance.pk).first()
    if not old:
        return

    # интересует только переход PENDING -> ACTIVE
    if old.status != AdvPromotion.Status.PENDING or instance.status != AdvPromotion.Status.ACTIVE:
        return

    # нельзя активировать без холда
    if not old.is_frozen:
        # откатываем статус
        instance.status = old.status
        return

    # проверяем статус в Stripe
    try:
        intent = stripe.PaymentIntent.retrieve(old.payment_id)
    except stripe.error.StripeError:
        instance.status = old.status
        return

    if intent.status != "requires_capture":
        instance.status = old.status
        return

    # делаем списание
    try:
        stripe.PaymentIntent.capture(old.payment_id)
    except stripe.error.StripeError:
        instance.status = old.status
        return

    # ВАЖНО: тут НЕ ставим is_paid=True.
    # Это сделает webhook на succeeded.