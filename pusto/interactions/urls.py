from django.urls import path
from .views import *

urlpatterns = [
    path('favorites/', favorites, name='favorites'),
    path("favorites/resolve/", resolve_favorites, name="resolve_favorites"),
    path("promotion/", promotion, name='promotion'),

    path('modal/', modal, name='modal'),
    path('notify/', notification_create, name='notification_create'),

    path('uk/notify/things/', notification_create_things, name='notify_things'),
    path('uk/notify/neighbor/', notification_create_neighbor, name='notify_neighbor'),
]