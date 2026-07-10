from django.shortcuts import render
from django.urls import path
from .views import *

urlpatterns = [

    path('support/submit/', support_submit, name='support_submit'),
    path('success/', success, name='success'),
    path('advertisingConfirmation/', confirmationView, name='confirmation'),
    path('claim/<str:app_label>/<str:model_name>/<int:object_id>/', create_claim, name='create_claim'),

    path("partner/<slug:slug>/", tracked_redirect, name="tracked_redirect"),
]
