from django.urls import path
from .views import *
from django.views.generic import RedirectView

app_name = 'ads'

urlpatterns = [
    path('', select, name='select'),
    path('search/', GlobalSearchView.as_view(), name='global_search'),

    path('things-add/<slug:slug>/', ThingsCreateView.as_view(), name='things_add'),
    path('things/<slug:slug>/', things.as_view(), name='things'),

    # path('jobs-add/<slug:slug>/', JobCreateView.as_view(), name='job_add'),
    # path('jobs/<slug:slug>/', jobs.as_view(), name='jobs'),

    path('neighbors-add/<slug:slug>/', NeighborCreateView.as_view(), name='neighbor_add'),
    path('neighbors/<slug:slug>/', neighbors.as_view(), name='neighbors'),

    path("page/<str:section>/<slug:title>-<int:id>/", page.as_view(), name="page"),
    path('relog/', relog, name='relog'),


    path('verify-post/<str:token>/', verify_post_email, name='verify_post_email'),
    path('resend-post-verification/', resend_post_verification, name='resend_post_verification'),

    path("send-message/<int:post_id>/", send_message, name="send_message"),
    path('favicon.ico', RedirectView.as_view(url='/static/favicon.ico')),

    path('things/', things.as_view(), name='things_all'),
    # path('jobs/', jobs.as_view(), name='jobs_all'),
    path('neighbors/', neighbors.as_view(), name='neighbors_all'),

    # documents
    path('privacy/', privacy, name='privacy'),
    path('terms/', terms, name='terms'),
    path('cookies/', cookies, name='cookies'),
    path('impressum/', impressum, name='impressum'),
    path('community', community, name='community'),
    path('paid_features/', paid_features, name='paid_features'),
    path('takedown/', takedown, name='takedown'),

    path("update-status/<str:ad_type>/<int:pk>/", UpdateAdStatusView.as_view(), name="update_ad_status"),

    path("robots.txt", TemplateView.as_view(template_name="ads/robots.txt", content_type="text/plain"), name="robots_txt"),

    path('similar/<str:section>/<slug:slug>/', similar, name='similar'),

    path('banner/<int:banner_id>/click/', banner_click, name='banner_click'),


]