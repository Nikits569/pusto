from django.urls import path
from .views import *
from .webhooks import stripe_webhook

urlpatterns = [
    # ---- TOP promotion ----
    path("top/select/<str:section>/<int:post_id>/", SelectTopPaymentView, name="select_top_payment"),
    path("top/create-intent/<str:section>/<int:post_id>/<str:duration>/", CreateTopPaymentIntentView.as_view(), name="create_top_intent"),
    path('payment-success/', PaymentSuccessView.as_view(), name='payment_success'),

    # ---- ADS ----
    path("ads/select/", SelectPaymentView.as_view(), name="select_payment"),
    path("ads/<slug:slug>/duration/", SelectAdvDurationView.as_view(), name="select_adv_duration"),
    path("ads/<slug:slug>/create/", AdvertisementCreateView.as_view(), name="create_ad"),
    path("ads/<slug:slug>/pay/", AdvertisementPaymentView.as_view(), name="ad_payment"),

    # ---- Stripe ----
    path("stripe/webhook/", stripe_webhook, name="stripe_webhook"),

    # (опционально) server-confirm endpoint — нужен только если ты хочешь confirm на backend
    # path("ads/confirm-intent/", create_payment_intent, name="confirm_adv_intent"),

    # ---- Admin tools ----
    path("stripe/debug/<int:pending_id>/", stripe_debug_pending, name="stripe_debug_pending"),
    path("admin/adv/<int:adv_id>/approve/", approve_adv, name="approve_adv"),
    path("admin/adv/<int:adv_id>/reject/", reject_adv, name="reject_adv"),

    # ---- Success ----
]