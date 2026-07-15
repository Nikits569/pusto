import datetime
import json
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.shortcuts import render
from ads.models import ThingsPost, JobPost, NeighborPost
from .pricing import get_price, get_all_tariffs
from .fx import eur_to_usdt
from .models import Order
from .qr import generate_qr_data_url
from .utils import generate_unique_amount
from decimal import Decimal, InvalidOperation

ORDER_TTL_MINUTES = 30

# post_type -> модель объявления (используется и для эндпоинта, и в кроне)
POST_MODEL_MAP = {
    "things": ThingsPost,
    "job": JobPost,
    "neighbor": NeighborPost,
}


@csrf_exempt
@require_http_methods(["POST"])
def create_order(request):
    """
    Ожидает JSON: {"amount": "25.00"}
    Возвращает данные для отрисовки QR на фронте.
    """
    try:
        body = json.loads(request.body)
        base_amount = Decimal(str(body["amount"]))
    except (json.JSONDecodeError, KeyError, ValueError):
        return JsonResponse({"error": "invalid payload"}, status=400)

    unique_amount = generate_unique_amount(base_amount)

    order = Order.objects.create(
        base_amount=base_amount,
        unique_amount=unique_amount,
        expires_at=timezone.now() + datetime.timedelta(minutes=ORDER_TTL_MINUTES),
    )

    return JsonResponse({
        "order_id": order.id,
        "amount": str(order.unique_amount),
        "currency": order.currency,
        "chain": order.chain,
        "address": settings.PAYMENT_DEPOSIT_ADDRESS,
        "qr_code": generate_qr_data_url(settings.PAYMENT_DEPOSIT_ADDRESS),
        "expires_at": order.expires_at.isoformat(),
        "type_order": order.TypeOrder.UPGRADE,
    })


@csrf_exempt
@require_http_methods(["POST"])
def create_promotion_order(request):
    """
    Ожидает JSON:
    {"post_type": "things", "post_id": 42, "duration_days": 7, "price_eur": "5.99"}

    post_type должен быть одним из POST_MODEL_MAP.
    Объявление должно принадлежать текущему пользователю — иначе 404,
    чтобы никто не мог оплатить продвижение чужого объявления.

    Если у пользователя уже есть неоплаченный и не истёкший заказ
    на этот же post_type/post_id/duration_days — возвращаем его же
    (тот же QR и сумму), а не создаём новый.
    """
    try:
        body = json.loads(request.body)
        post_type = body["post_type"]
        post_id = int(body["post_id"])
        duration_days = int(body["duration_days"])
        price_eur = Decimal(str(body["price_eur"]))
    except (json.JSONDecodeError, KeyError, ValueError, TypeError):
        return JsonResponse({"error": "invalid payload"}, status=400)

    PostModel = POST_MODEL_MAP.get(post_type)
    if PostModel is None:
        return JsonResponse({"error": "unknown post_type"}, status=400)

    # 404 если объявления нет или оно принадлежит не этому пользователю
    get_object_or_404(PostModel, id=post_id, user=request.user)

    # ищем уже существующий неоплаченный и не истёкший заказ на этот же тариф —
    # чтобы повторное открытие крипто-оплаты не плодило новые заказы с новым QR
    existing_order = Order.objects.filter(
        user=request.user,
        post_type=post_type,
        post_id=post_id,
        duration_days=duration_days,
        payment_method=Order.PaymentMethod.CRYPTO,
        status=Order.Status.PENDING,
        expires_at__gt=timezone.now(),
    ).first()

    if existing_order:
        order = existing_order
    else:
        base_amount = eur_to_usdt(price_eur)
        unique_amount = generate_unique_amount(base_amount)

        order = Order.objects.create(
            user=request.user,
            base_amount=base_amount,
            unique_amount=unique_amount,
            post_type=post_type,
            post_id=post_id,
            duration_days=duration_days,
            price_eur=price_eur,
            expires_at=timezone.now() + datetime.timedelta(minutes=ORDER_TTL_MINUTES),
        )

    expected_price = get_price(Order.TypeOrder.UPGRADE, duration_days)
    if expected_price is None or expected_price != price_eur:
        return JsonResponse({"error": "price mismatch, refresh the page"}, status=400)

    return JsonResponse({
        "order_id": order.id,
        "amount": str(order.unique_amount),
        "currency": order.currency,
        "chain": order.chain,
        "address": settings.PAYMENT_DEPOSIT_ADDRESS,
        "qr_code": generate_qr_data_url(settings.PAYMENT_DEPOSIT_ADDRESS),
        "expires_at": order.expires_at.isoformat(),
        "type_order": order.TypeOrder.UPGRADE,

    })

@csrf_exempt
@require_http_methods(["POST"])
def create_manual_promotion_order(request):
    """
    Заказ на продвижение через способ оплаты без автоматической проверки
    (Revolut, українська картка). Никакого QR/крипты — просто фиксируем
    заявку с контактом клиента, дальше администратор вручную подтверждает
    оплату в админке (после чего объявление поднимется автоматически).

    Ожидает JSON:
    {
      "post_type": "things", "post_id": 42, "duration_days": 7,
      "price_eur": "5.99", "payment_method": "revolut", "contact": "@username"
    }
    """
    try:
        body = json.loads(request.body)
        post_type = body["post_type"]
        post_id = int(body["post_id"])
        duration_days = int(body["duration_days"])
        price_eur = Decimal(str(body["price_eur"]))
        payment_method = body["payment_method"]
        contact = str(body.get("contact", "")).strip()
    except (json.JSONDecodeError, KeyError, ValueError, TypeError):
        return JsonResponse({"error": "invalid payload"}, status=400)

    if payment_method not in (Order.PaymentMethod.REVOLUT, Order.PaymentMethod.CARD_UA):
        return JsonResponse({"error": "invalid payment_method"}, status=400)

    if not contact:
        return JsonResponse({"error": "contact is required"}, status=400)

    PostModel = POST_MODEL_MAP.get(post_type)
    if PostModel is None:
        return JsonResponse({"error": "unknown post_type"}, status=400)

    get_object_or_404(PostModel, id=post_id, user=request.user)

    MAX_MANUAL_REQUESTS = 5

    manual_requests_count = Order.objects.filter(
        user=request.user,
        payment_method__in=[Order.PaymentMethod.REVOLUT, Order.PaymentMethod.CARD_UA],
    ).count()

    if manual_requests_count >= MAX_MANUAL_REQUESTS:
        return JsonResponse(
            {"error": "Ви досягли ліміту запитів на оплату. Зверніться до адміністратора напряму."},
            status=429,
        )

    order = Order.objects.create(
        user=request.user,
        payment_method=payment_method,
        contact=contact,
        post_type=post_type,
        post_id=post_id,
        duration_days=duration_days,
        price_eur=price_eur,
    )

    method_label = order.get_payment_method_display()

    # письмо администратору — есть новая заявка на ручную оплату
    send_mail(
        subject=f"Нова заявка на оплату ({method_label}) — заказ #{order.id}",
        message=(
            f"Користувач: {request.user.email or request.user.username} (id={request.user.id})\n"
            f"Оголошення: {post_type} #{post_id}\n"
            f"Тариф: {duration_days} днів, {price_eur} €\n"
            f"Спосіб оплати: {method_label}\n"
            f"Контакт клієнта: {contact}\n\n"
            f"Підтвердіть оплату вручну в адмінці, коли гроші надійдуть."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[settings.ADMIN_NOTIFICATION_EMAIL],
        fail_silently=False,
    )

    # письмо пользователю — просим подождать
    if request.user.email:
        send_mail(
            subject="Ваш запит на оплату отримано",
            message=(
                f"Дякуємо! Ваш запит на оплату ({method_label}) отримано.\n"
                f"Очікуйте, наш адміністратор незабаром зв'яжеться з вами "
                f"за контактом: {contact}."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[request.user.email],
            fail_silently=True,
        )

    expected_price = get_price(Order.TypeOrder.UPGRADE, duration_days)
    if expected_price is None or expected_price != price_eur:
        return JsonResponse({"error": "price mismatch, refresh the page"}, status=400)

    return JsonResponse({
        "order_id": order.id,
        "payment_method": order.payment_method,
        "type_order": order.TypeOrder.UPGRADE,


    })


@require_http_methods(["GET"])
def order_status(request, order_id: int):
    try:
        order = Order.objects.get(id=order_id)
    except Order.DoesNotExist:
        return JsonResponse({"error": "not found"}, status=404)

    if order.is_expired():
        order.status = Order.Status.EXPIRED
        order.save(update_fields=["status"])

    return JsonResponse({
        "status": order.status,
        "type_order": order.TypeOrder.UPGRADE,
        "paid_at": order.paid_at.isoformat() if order.paid_at else None,
    })


csrf_exempt


@require_http_methods(["POST"])
def submit_ad_content(request):
    """
    Заявка на рекламный пост/баннер.

    В отличие от create_promotion_order/create_manual_promotion_order,
    здесь пользователь СРАЗУ загружает креатив (фото + текст + опционально
    ссылку) и оставляет контакт. Оплата НЕ автоматизирована ни для одного
    способа — админ сам списывается с клиентом, договаривается об оплате
    и вручную переводит Order.status в PAID + публикует рекламу
    (через отдельный процесс/админку, вне этого файла).

    Ожидает multipart/form-data (не JSON — из-за файла):
      type_order:     "post" | "banner"
      duration_days:  int
      price_eur:      str  (сверяется с pricing.json)
      contact:        str  (email / @telegram / телефон)
      ad_text:        str
      ad_link:        str  (опционально)
      ad_image:       file (опционально, но рекомендуем делать required на фронте)
    """
    type_order = request.POST.get("type_order")
    if type_order not in (Order.TypeOrder.POST, Order.TypeOrder.BANNER):
        return JsonResponse({"error": "invalid type_order"}, status=400)

    try:
        duration_days = int(request.POST.get("duration_days"))

        raw_price = (request.POST.get("price_eur") or "").replace(",", ".").strip()
        price_eur = Decimal(raw_price)
    except (TypeError, ValueError, InvalidOperation):
        return JsonResponse({"error": "invalid payload"}, status=400)

    contact = request.POST.get("contact", "").strip()
    ad_text = request.POST.get("ad_text", "").strip()
    ad_link = request.POST.get("ad_link", "").strip()
    ad_image = request.FILES.get("ad_image")

    if not contact:
        return JsonResponse({"error": "contact is required"}, status=400)
    if not ad_text:
        return JsonResponse({"error": "ad_text is required"}, status=400)

    # сверяем цену с прайсом на сервере — не доверяем тому, что прислал фронт
    expected_price = get_price(type_order, duration_days)
    if expected_price is None or expected_price != price_eur:
        return JsonResponse({"error": "price mismatch, refresh the page"}, status=400)

    MAX_AD_SUBMISSIONS = 5
    submissions_count = Order.objects.filter(
        user=request.user,
        type_order__in=[Order.TypeOrder.POST, Order.TypeOrder.BANNER],
    ).count()
    if submissions_count >= MAX_AD_SUBMISSIONS:
        return JsonResponse(
            {"error": "Ви досягли ліміту заявок на рекламу. Зверніться до адміністратора напряму."},
            status=429,
        )

    order = Order.objects.create(
        user=request.user,
        type_order=type_order,
        duration_days=duration_days,
        price_eur=price_eur,
        contact=contact,
        ad_text=ad_text,
        ad_link=ad_link or None,
        ad_image=ad_image,
        status=Order.Status.PENDING,  # ждём, пока админ вручную договорится об оплате
    )

    format_label = order.get_type_order_display()

    send_mail(
        subject=f"Нова заявка на рекламу ({format_label}) — заказ #{order.id}",
        message=(
            f"Користувач: {request.user.email or request.user.username} (id={request.user.id})\n"
            f"Формат: {format_label}, {duration_days} днів, {price_eur} €\n"
            f"Контакт клієнта: {contact}\n\n"
            f"Текст оголошення:\n{ad_text}\n\n"
            f"Посилання: {ad_link or '—'}\n"
            f"Фото додано: {'так' if ad_image else 'ні'}\n\n"
            f"Домовтесь з клієнтом про оплату вручну. Після надходження оплати "
            f"підтвердіть заказ #{order.id} в адмінці і опублікуйте рекламу."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[settings.ADMIN_NOTIFICATION_EMAIL],
        fail_silently=False,
    )

    if request.user.email:
        send_mail(
            subject="Вашу заявку на рекламу отримано",
            message=(
                f"Дякуємо! Заявку на рекламу ({format_label}, {duration_days} днів, "
                f"{price_eur} €) отримано.\n"
                f"Наш адміністратор зв'яжеться з вами за контактом «{contact}» "
                f"щодо оплати."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[request.user.email],
            fail_silently=True,
        )

    return JsonResponse({
        "order_id": order.id,
        "status": order.status,
        "type_order": order.type_order,
    })


def select_adv(request):
    tariffs = get_all_tariffs()
    return render(request, "payments/select_adv_duration.html", {
        "post_tariffs": tariffs.get("post", []),
        "banner_tariffs": tariffs.get("banner", []),
    })

def partnership(request):
    return render(request, "payments/partnership.html")