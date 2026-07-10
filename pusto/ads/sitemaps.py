from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from .models import ThingsPost
from django.utils.text import slugify


def make_post_slug(title, fallback="post"):
    slug = slugify(title or "", allow_unicode=False)
    return slug or fallback

class ThingsSitemap(Sitemap):
    changefreq = "daily"
    priority = 0.8

    def items(self):
        bad_words = [
            "kto znaet",
            "privet",
            "infa",
            "ls",
            "nalichka",
            "uah",
            "u-kogo"
        ]

        qs = (
            ThingsPost.objects
            .exclude(text="<без текста>")
            .exclude(title__isnull=True)
            .exclude(title="")
        )

        for word in bad_words:
            qs = qs.exclude(title__icontains=word)

        return qs

    def lastmod(self, obj):
        return obj.created_at

    def location(self, obj):
        title_slug = make_post_slug(obj.slug_title, fallback="post")

        return reverse("ads:page", kwargs={
            "section": "things",
            "title": title_slug,
            "id": obj.id,
        })

class StaticSitemap(Sitemap):
    priority = 1.0
    changefreq = "daily"

    def items(self):
        return [
            "things_all",
            "neighbors_all",

            # Rent SEO
            "rent_presov",
            "rent_bratislava",
            "rent_kosice",

            # Things SEO
            "things_presov",
            "things_bratislava",
            "things_kosice",
        ]

    def location(self, item):
        seo_urls = {
            "rent_presov": "/rent/presov/",
            "rent_bratislava": "/rent/bratislava/",
            "rent_kosice": "/rent/kosice/",

            "things_presov": "/things/presov/",
            "things_bratislava": "/things/bratislava/",
            "things_kosice": "/things/kosice/",
        }

        if item in seo_urls:
            return seo_urls[item]

        return reverse(f"ads:{item}")