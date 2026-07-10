import json
import stripe
import uuid
from django.conf import settings
from django.core.mail import send_mail
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.views import View
from django.views.generic import TemplateView, FormView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.contenttypes.models import ContentType
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.http import require_POST
from django.db import transaction
from django.db.utils import IntegrityError
from .forms import AdvertisementForm
from .models import PendingAdvPromotion, AdvPromotion, TopPromotion, StripeWebhookEvent
from ads.models import ThingsPost, JobPost, NeighborPost

stripe.api_key = settings.STRIPE_SECRET_KEY


def _sess_key(base: str, slug: str) -> str:
    return f"{base}:{slug}"


POST_MODELS = {
    "things": ThingsPost,
    "job": JobPost,
    "neighbor": NeighborPost,
}

ADV_DURATION_PRICE = {
    "7": 500,
    "30": 3000,
    "90": 8000,
}

TOP_DURATION_PRICE = {
    "3": 250,
    "7": 500,
    "14": 900,
}


# -------------------------
# ADS: type -> duration -> create -> pay
# -------------------------

class SelectAdvDurationView(LoginRequiredMixin, View):
    template_name = "payments/select_adv_duration.html"
    ALLOWED = set(ADV_DURATION_PRICE.keys())

    def get(self, request, slug):
        return render(request, self.template_name, {"ad_type": slug})

    def post(self, request, slug):
        duration = request.POST.get("duration")
        if duration not in self.ALLOWED:
            return render(request, self.template_name, {"ad_type": slug, "error": "Неверный срок"})

        # Храним duration строго по slug (чтобы вкладки не мешали)
        request.session[_sess_key("adv_duration", slug)] = duration

        # Сбрасываем только "свои" ключи
        request.session.pop(_sess_key("adv_intent_id", slug), None)
        request.session.pop(_sess_key("pending_id", slug), None)

        return redirect("create_ad", slug=slug)

class AdvertisementCreateView(LoginRequiredMixin, FormView):
    template_name = "payments/ad_payment.html"
    form_class = AdvertisementForm

    def dispatch(self, request, *args, **kwargs):
        slug = self.kwargs.get("slug")
        duration = request.session.get(_sess_key("adv_duration", slug))
        if not duration:
            return redirect("select_adv_duration", slug=slug)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        slug = self.kwargs.get("slug")

        duration = self.request.session.get(_sess_key("adv_duration", slug))
        price_cents = ADV_DURATION_PRICE.get(str(duration)) if duration else None

        ctx["slug"] = slug
        ctx["duration"] = duration
        ctx["price"] = (price_cents // 100) if price_cents else None  # евро
        return ctx

    def form_valid(self, form):
        slug = self.kwargs["slug"]

        # ВАЖНО:
        # В session храним только имя файла (строку), не сам файл.
        # Если тебе нужен реальный файл на этапе оплаты — сохраняй его в модель/временное хранилище.
        image_name = None
        if form.cleaned_data.get("image"):
            image_name = form.cleaned_data["image"].name

        # храним данные формы по slug
        ad_map = self.request.session.get("ad_form_data_map", {})
        ad_map[slug] = {
            "title": form.cleaned_data["title"],
            "link": form.cleaned_data.get("link"),
            "image": image_name,
            "ad_type": slug,
        }
        self.request.session["ad_form_data_map"] = ad_map

        # сбрасываем все payment-сессионные ключи для этого slug,
        # чтобы новая попытка оплаты создала новый PaymentIntent + Pending.
        for k in ("adv_intent_id", "pending_id", "checkout_key"):
            self.request.session.pop(_sess_key(k, slug), None)

        self.request.session.modified = True
        return redirect("ad_payment", slug=slug)

stripe.api_key = settings.STRIPE_SECRET_KEY

def _sess_key(name: str, slug: str) -> str:
    return f"adv:{slug}:{name}"

class AdvertisementPaymentView(LoginRequiredMixin, View):
    template_name = "payments/pay.html"

    def _ensure_checkout_key(self, request, slug) -> str:
        key = request.session.get(_sess_key("checkout_key", slug))
        if not key:
            key = str(uuid.uuid4())
            request.session[_sess_key("checkout_key", slug)] = key
            request.session.modified = True
        return key

    def _rotate_checkout_key(self, request, slug) -> str:
        key = str(uuid.uuid4())
        request.session[_sess_key("checkout_key", slug)] = key
        request.session.pop(_sess_key("adv_intent_id", slug), None)
        request.session.pop(_sess_key("pending_id", slug), None)
        request.session.modified = True
        return key

    def _get_amount(self, duration: str) -> int:
        from .views import ADV_DURATION_PRICE  # или откуда у тебя
        amount = ADV_DURATION_PRICE.get(str(duration))
        if not amount:
            raise ValueError("Неверная длительность")
        return amount

    def _render(self, request, slug, duration, intent):
        return render(
            request,
            self.template_name,
            {
                "client_secret": intent.client_secret,
                "STRIPE_PUBLIC_KEY": settings.STRIPE_PUBLIC_KEY,
                "ad_type": slug,
                "duration": int(duration),
                "price": intent.amount,
            },
        )

    def get(self, request, slug):
        ad_data = request.session.get("ad_form_data_map", {}).get(slug)
        duration = request.session.get(_sess_key("adv_duration", slug))

        if not duration:
            return redirect("select_adv_duration", slug=slug)
        if not ad_data:
            return redirect("create_ad", slug=slug)

        checkout_key = self._ensure_checkout_key(request, slug)

        # 0) reuse intent from session
        intent_id = request.session.get(_sess_key("adv_intent_id", slug))
        if intent_id:
            try:
                intent = stripe.PaymentIntent.retrieve(intent_id)
            except stripe.error.StripeError:
                checkout_key = self._rotate_checkout_key(request, slug)
            else:
                if intent.status in ("succeeded", "canceled"):
                    checkout_key = self._rotate_checkout_key(request, slug)
                else:
                    return self._render(request, slug, duration, intent)

        # 1) restore via pending
        existing = PendingAdvPromotion.objects.filter(
            checkout_key=checkout_key,
            user=request.user,
        ).first()

        if existing:
            request.session[_sess_key("pending_id", slug)] = existing.id
            request.session[_sess_key("adv_intent_id", slug)] = existing.payment_intent_id
            request.session.modified = True

            try:
                intent = stripe.PaymentIntent.retrieve(existing.payment_intent_id)
            except stripe.error.StripeError:
                checkout_key = self._rotate_checkout_key(request, slug)
            else:
                if intent.status in ("succeeded", "canceled"):
                    checkout_key = self._rotate_checkout_key(request, slug)
                else:
                    return self._render(request, slug, duration, intent)

        # 2) create new PI (manual capture) + pending + adv
        try:
            amount = self._get_amount(duration)
        except ValueError:
            return HttpResponse("Неверная длительность", status=400)

        stripe_idem = f"adv:{request.user.id}:{slug}:{checkout_key}"

        # ✅ ВАЖНО:
        # - оставляем automatic_payment_methods для Payment Element
        # - НЕ передаем confirmation_method (иначе ошибка)
        # - capture_method="manual" включает HOLD (requires_capture)
        intent = stripe.PaymentIntent.create(
            amount=amount,
            currency="eur",
            capture_method="manual",
            automatic_payment_methods={"enabled": True},
            metadata={
                "payment_type": "adv_promotion",
                "user_id": str(request.user.id),
                "ad_type": slug,
                "duration": str(duration),
                "checkout_key": str(checkout_key),
            },
            idempotency_key=stripe_idem,
        )

        print("VIEW CREATED PI:", intent.id, "status:", intent.status, "meta:", intent.metadata)

        try:
            with transaction.atomic():
                pending = PendingAdvPromotion.objects.create(
                    user=request.user,
                    title=ad_data["title"],
                    link=ad_data.get("link"),
                    image=ad_data.get("image"),
                    ad_type=slug,
                    payment_intent_id=intent.id,
                    duration_days=int(duration),
                    checkout_key=checkout_key,
                )

                # дописываем pending_id в metadata PI
                try:
                    stripe.PaymentIntent.modify(
                        intent.id,
                        metadata={**(intent.metadata or {}), "pending_id": str(pending.id)},
                    )
                except stripe.error.StripeError as e:
                    print("PI modify metadata failed:", e)

                AdvPromotion.objects.get_or_create(
                    payment_id=intent.id,
                    defaults=dict(
                        user=request.user,
                        title=ad_data["title"],
                        link=ad_data.get("link"),
                        image=ad_data.get("image"),
                        ad_type=slug,
                        is_paid=False,
                        is_frozen=False,  # станет True через webhook при requires_capture
                        duration_days=int(duration),
                        status=AdvPromotion.Status.PENDING,
                    ),
                )

        except IntegrityError:
            pending = PendingAdvPromotion.objects.get(checkout_key=checkout_key, user=request.user)
            intent = stripe.PaymentIntent.retrieve(pending.payment_intent_id)

        request.session[_sess_key("adv_intent_id", slug)] = intent.id
        request.session[_sess_key("pending_id", slug)] = pending.id
        request.session.modified = True

        return self._render(request, slug, duration, intent)

    def post(self, request, slug):
        return redirect("ad_payment", slug=slug)

@require_POST
def create_payment_intent(request):
    """
    CONFIRM существующего PaymentIntent (manual capture).
    НЕ создаём новый intent.
    """
    try:
        data = json.loads(request.body or "{}")
    except Exception:
        return JsonResponse({"error": "Bad JSON"}, status=400)

    slug = data.get("slug")
    payment_method_id = data.get("payment_method")

    if not slug:
        return JsonResponse({"error": "slug required"}, status=400)
    if not payment_method_id:
        return JsonResponse({"error": "payment_method required"}, status=400)

    pending_id = request.session.get(_sess_key("pending_id", slug))
    intent_id = request.session.get(_sess_key("adv_intent_id", slug))

    if not pending_id:
        return JsonResponse({"error": "pending_id missing in session"}, status=400)
    if not intent_id:
        return JsonResponse({"error": "intent_id missing in session"}, status=400)

    pending = PendingAdvPromotion.objects.filter(id=pending_id, user=request.user).first()
    if not pending:
        return JsonResponse({"error": "Pending ad not found"}, status=404)

    if pending.payment_intent_id != intent_id:
        return JsonResponse({"error": "Intent mismatch"}, status=400)

    ad = AdvPromotion.objects.filter(payment_id=intent_id, user=request.user).first()
    if ad and ad.is_paid:
        return JsonResponse({"error": "Already paid"}, status=400)

    try:
        intent = stripe.PaymentIntent.retrieve(intent_id)

        if intent.status in ("requires_capture", "succeeded", "processing"):
            return JsonResponse({"client_secret": intent.client_secret, "status": intent.status})

        if intent.status in ("requires_payment_method", "requires_confirmation", "requires_action"):
            intent = stripe.PaymentIntent.confirm(intent_id, payment_method=payment_method_id)
            return JsonResponse({"client_secret": intent.client_secret, "status": intent.status})

        return JsonResponse({"error": f"Unexpected intent status: {intent.status}"}, status=400)

    except stripe.error.StripeError as e:
        return JsonResponse({"error": str(e)}, status=400)


# -------------------------
# TOP promotion (обычная оплата)
# -------------------------

class CreateTopPaymentIntentView(LoginRequiredMixin, View):
    def post(self, request, section, post_id, duration):
        model = POST_MODELS.get(section)
        if not model:
            return HttpResponse("Неверная секция", status=400)

        post = get_object_or_404(model, pk=post_id)

        price_cents = TOP_DURATION_PRICE.get(str(duration))
        if not price_cents:
            return HttpResponse("Неверная длительность", status=400)

        intent = stripe.PaymentIntent.create(
            amount=price_cents,
            currency="eur",
            metadata={
                "payment_type": "top_promotion",
                "section": section,
                "post_id": str(post.id),
                "duration": str(duration),
            }
        )

        TopPromotion.objects.create(
            user=request.user,
            content_type=ContentType.objects.get_for_model(post),
            object_id=post.id,
            payment_id=intent.id,
            is_paid=False,
            duration_days=int(duration),
        )

        return render(request, "payments/top_payment.html", {
            "section": section,
            "post": post,
            "price": intent.amount,
            "client_secret": intent.client_secret,
            "STRIPE_PUBLIC_KEY": settings.STRIPE_PUBLIC_KEY,
        })

class SelectPaymentView(TemplateView):
    template_name = "payments/select_payment.html"

def SelectTopPaymentView(request, ad_type, section, post_id):
    model = POST_MODELS.get(section)
    if not model:
        return HttpResponse("Неверная секция", status=400)

    post = get_object_or_404(model, pk=post_id)

    return render(request, "payments/select_top_payment.html", {
        "section": section,
        "post": post,
        "ad_type": ad_type,
    })

class PaymentSuccessView(TemplateView):
    template_name = "payments/payment_success.html"


# -------------------------
# Admin-only tools
# -------------------------

@staff_member_required
def stripe_debug_pending(request, pending_id: int):
    pending = get_object_or_404(PendingAdvPromotion, id=pending_id)
    events = StripeWebhookEvent.objects.filter(pending_id=pending.id).order_by("-created_at")
    return render(request, "payments/stripe_debug.html", {
        "pending": pending,
        "events": events,
    })


@staff_member_required
@require_POST
def approve_adv(request, adv_id: int):
    adv = get_object_or_404(AdvPromotion, id=adv_id)

    if adv.status != AdvPromotion.Status.PENDING:
        return HttpResponse("Нельзя approve: не PENDING", status=400)
    if not adv.is_frozen:
        return HttpResponse("Нельзя approve: нет холда (is_frozen=False)", status=400)

    intent = stripe.PaymentIntent.retrieve(adv.payment_id)
    if intent.status != "requires_capture":
        return HttpResponse(f"Нельзя capture, статус: {intent.status}", status=400)

    stripe.PaymentIntent.capture(adv.payment_id)
    return redirect("admin:payments_advpromotion_change", adv.id)

@staff_member_required
@require_POST
def reject_adv(request, adv_id: int):
    adv = get_object_or_404(AdvPromotion, id=adv_id)

    if adv.status != AdvPromotion.Status.PENDING:
        return HttpResponse("Нельзя reject: не PENDING", status=400)

    intent = stripe.PaymentIntent.retrieve(adv.payment_id)
    if intent.status in ("requires_capture", "requires_action", "requires_confirmation", "requires_payment_method"):
        stripe.PaymentIntent.cancel(adv.payment_id)

    adv.status = AdvPromotion.Status.REJECTED
    adv.is_paid = False
    adv.is_frozen = False
    adv.save(update_fields=["status", "is_paid", "is_frozen"])

    return redirect("admin:payments_advpromotion_change", adv.id)

class PaymentSuccessView(View):
    def get(self, request):
        user = request.user

        first_name = user.first_name or ""
        last_name = user.last_name or ""

        send_mail(
            subject='Оплата прошла успешно',
            message=(
                f'Здравствуйте, {first_name} {last_name}!\n\n'
                'Ваш платёж успешно обработан.\n'
                'Проверьте почту — мы отправили подтверждение.'
            ),
            from_email='noreply@yourdomain.com',
            recipient_list=[user.email],
            fail_silently=False,
        )

        return render(request, "payments/success_payment.html", {
            "first_name": first_name,
            "last_name": last_name,
        })