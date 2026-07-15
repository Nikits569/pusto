from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.conf.urls.i18n import set_language
from django.contrib.sitemaps.views import sitemap
from ads.sitemaps import ThingsSitemap, StaticSitemap
from django.conf.urls.i18n import set_language
from django.conf.urls.i18n import i18n_patterns
from django.views.generic import RedirectView
from .views import *
sitemaps = {
    "things": ThingsSitemap,
    "static": StaticSitemap,
}

urlpatterns = [
    path("", RedirectView.as_view(url="/uk/", permanent=False)),
    path("i18n/setlang/", custom_set_language, name="set_language"),
]


urlpatterns += i18n_patterns(
    path('admin/', admin.site.urls),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='sitemap'),
    path('', include('ads.urls')),
    path('', include('accounts.urls')),
    path('', include('profiles.urls')),
    path('', include('interactions.urls')),
    path('', include('support.urls')),
    path('', include('SEO.urls')),
    path('payments/', include('payments.urls')),
)

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

#if settings.DEBUG:
#    import debug_toolbar
#    urlpatterns += [
#        path("__debug__/", include(debug_toolbar.urls)),
#    ]