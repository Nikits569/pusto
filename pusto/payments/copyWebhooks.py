

from __future__ import annotations

from datetime import timedelta
import stripe

from django.conf import settings
from django.http import HttpResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import PendingAdvPromotion, AdvPromotion, StripeWebhookEvent

stripe.api_key = settings.STRIPE_SECRET_KEY


@csrf_exempt
@require_http_methods(["POST", "GET"])
def stripe_webhook(request):
    print("WEBHOOK HIT", request.method, "sig?", bool(request.META.get("HTTP_STRIPE_SIGNATURE")))
    if request.method == "GET":
        return HttpResponse("ok", status=200)

    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")

    try:
        is_dev = settings.DEBUG

        if is_dev:
            # локально доверяем CLI, просто парсим JSON
            import json
            event = json.loads(request.body.decode("utf-8"))
        else:
            # прод: строгая подпись
            event = stripe.Webhook.construct_event(
                payload=request.body,
                sig_header=request.META.get("HTTP_STRIPE_SIGNATURE", ""),
                secret=settings.STRIPE_WEBHOOK_SECRET,
            )
    except Exception as e:
        print("WEBHOOK VERIFY FAILED:", repr(e))
        return HttpResponse(status=400)

    event_id = event.get("id")
    event_type = event.get("type") or ""
    obj = (event.get("data") or {}).get("object") or {}

    intent_id = None
    status = None
    metadata = {}
    amount = None
    amount_capturable = None

    # ---- Extract PI info ----
    if obj.get("object") == "payment_intent":
        intent_id = obj.get("id")
        status = obj.get("status")
        metadata = obj.get("metadata") or {}
        amount = obj.get("amount")
        amount_capturable = obj.get("amount_capturable")

    elif obj.get("object") == "charge":
        # fallback: charge.* -> достаем PI
        intent_id = obj.get("payment_intent")
        if not intent_id:
            print("WEBHOOK:", event_type, "charge without payment_intent -> ignore")
            return HttpResponse(status=200)

        try:
            pi = stripe.PaymentIntent.retrieve(intent_id)
        except stripe.error.StripeError as e:
            print("PI RETRIEVE FAILED:", intent_id, repr(e))
            return HttpResponse(status=200)

        status = pi.get("status")
        metadata = pi.get("metadata") or {}
        amount = pi.get("amount")
        amount_capturable = pi.get("amount_capturable")

    else:
        # нам неинтересно
        return HttpResponse(status=200)

    now = timezone.now()

    md_pending = metadata.get("pending_id")
    pending_id_from_md = int(md_pending) if str(md_pending or "").isdigit() else None

    print(
        "WEBHOOK:",
        "event=", event_type,
        "evt_id=", event_id,
        "pi=", intent_id,
        "status=", status,
        "pending_id=", pending_id_from_md,
        "amount=", amount,
        "capturable=", amount_capturable,
    )

    # ---- Idempotency on event_id ----
    obj_event, created = StripeWebhookEvent.objects.get_or_create(
        event_id=event_id,
        defaults={
            "event_type": event_type,
            "payment_intent_id": intent_id,
            "pending_id": pending_id_from_md,
            "status": status,
            "amount": amount,
            "amount_capturable": amount_capturable,
            "livemode": bool(event.get("livemode", False)),
            "payload": _maybe_json(payload),
        },
    )
    if not created:
        print("WEBHOOK DUPLICATE EVENT:", event_id, "-> ignore")
        return HttpResponse(status=200)

    # ---- Load Pending (prefer metadata.pending_id) ----
    pending = None
    if pending_id_from_md:
        pending = PendingAdvPromotion.objects.filter(id=pending_id_from_md).first()

    if not pending:
        pending = PendingAdvPromotion.objects.filter(payment_intent_id=intent_id).first()

    if pending:
        PendingAdvPromotion.objects.filter(id=pending.id).update(
            last_webhook_event=event_type,
            last_webhook_at=now,
            last_intent_status=status,
        )

    # ---- Load/Create AdvPromotion (prefer payment_id) ----
    ad = AdvPromotion.objects.filter(payment_id=intent_id).first()

    # Если ad не нашли — создадим из pending (это главный фикс)
    if not ad and pending:
        ad, _ = AdvPromotion.objects.get_or_create(
            payment_id=intent_id,
            defaults=dict(
                user=pending.user,
                title=pending.title,
                link=pending.link,
                image=pending.image,
                ad_type=pending.ad_type,
                duration_days=pending.duration_days,
                status=AdvPromotion.Status.PENDING,
                is_paid=False,
                is_frozen=False,
            ),
        )

    # Обновим last_* даже если ad был создан/найден
    AdvPromotion.objects.filter(payment_id=intent_id).update(
        last_intent_status=status,
        last_webhook_at=now,
        last_webhook_event=event_type,
    )

    # duration_days безопасно
    duration_days = 0
    if ad and ad.duration_days:
        duration_days = int(ad.duration_days)
    elif pending and pending.duration_days:
        duration_days = int(pending.duration_days)
    else:
        d = metadata.get("duration")
        if str(d or "").isdigit():
            duration_days = int(d)

    # ---- State machine ----

    # HOLD: деньги авторизованы, но не списаны (manual capture)
    if status == "requires_capture":
        rows = AdvPromotion.objects.filter(payment_id=intent_id).update(
            is_frozen=True,
            is_paid=False,
            status=AdvPromotion.Status.PENDING,
        )
        print("SET FROZEN:", intent_id, "rows=", rows)
        return HttpResponse(status=200)

    # CAPTURED: деньги списаны
    if status == "succeeded":
        rows = AdvPromotion.objects.filter(payment_id=intent_id).update(
            is_frozen=False,
            is_paid=True,
            status=AdvPromotion.Status.ACTIVE,
            starts_at=now,
            ends_at=now + timedelta(days=duration_days),
        )
        print("SET PAID:", intent_id, "rows=", rows, "days=", duration_days)
        return HttpResponse(status=200)

    # В процессе/ожидает действий
    if status in ("processing", "requires_action", "requires_confirmation", "requires_payment_method"):
        rows = AdvPromotion.objects.filter(payment_id=intent_id).update(
            is_frozen=False,
            is_paid=False,
            status=AdvPromotion.Status.PENDING,
        )
        print("SET PENDING:", intent_id, "rows=", rows)
        return HttpResponse(status=200)

    # Отменен
    if status == "canceled":
        rows = AdvPromotion.objects.filter(payment_id=intent_id).update(
            is_frozen=False,
            is_paid=False,
            status=AdvPromotion.Status.REJECTED,
        )
        print("SET CANCELED:", intent_id, "rows=", rows)
        return HttpResponse(status=200)

    print("WEBHOOK UNHANDLED STATUS:", status, "PI:", intent_id)
    return HttpResponse(status=200)


def _maybe_json(payload_bytes):
    try:
        import json
        return json.loads(payload_bytes.decode("utf-8"))
    except Exception:
        return None