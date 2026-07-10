from django.urls import path
from .views import *

urlpatterns = [
    path('favorites/', favorites, name='favorites'),
    path("favorites/resolve/", resolve_favorites, name="resolve_favorites"),
    path("promotion/", promotion, name='promotion'),
]