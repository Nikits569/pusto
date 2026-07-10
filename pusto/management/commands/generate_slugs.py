from django.core.management.base import BaseCommand
from django.utils.text import slugify
from unidecode import unidecode

from your_app.models import ThingsPost


class Command(BaseCommand):
    help = "Generate slug_title for existing ThingsPost"

    def handle(self, *args, **options):
        qs = ThingsPost.objects.filter(slug_title__isnull=True) | \
             ThingsPost.objects.filter(slug_title='')

        total = qs.count()
        self.stdout.write(f"Found {total} objects without slug")

        for i, obj in enumerate(qs.iterator(chunk_size=500), start=1):
            if obj.title:
                obj.slug_title = slugify(unidecode(obj.title))
                obj.save(update_fields=['slug_title'])

            if i % 500 == 0:
                self.stdout.write(f"Processed {i}/{total}")

        self.stdout.write(self.style.SUCCESS("Done!"))
