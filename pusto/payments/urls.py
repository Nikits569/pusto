from django.urls import path

from . import views

urlpatterns = [
    path("orders/create/", views.create_order, name="create_order"),
    path("promotions/create/", views.create_promotion_order, name="create_promotion_order"),
    path(
        "promotions/create-manual/",
        views.create_manual_promotion_order,
        name="create_manual_promotion_order",
    ),
    ### ДОБАВИТЬ эту строку:
    path("ads/submit/", views.submit_ad_content, name="submit_ad_content"),
    path("orders/<int:order_id>/status/", views.order_status, name="order_status"),
    path('select_advertising/', views.select_adv, name='select_adv'),
    path('partnership/', views.partnership, name='partnership'),
]