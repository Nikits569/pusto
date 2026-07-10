from django.urls import path
from .views import *

urlpatterns = [
    path('byty-<slug:slug>/', rent, name='rent_seo'),
    path('things-<slug:slug>/', things, name='things_seo'),
]