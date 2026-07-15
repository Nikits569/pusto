from django.core.management.base import BaseCommand
from django.utils import timezone

from ads.models import ThingsPost, JobPost, NeighborPost, PrivateStatus

MODELS = [ThingsPost, JobPost, NeighborPost]


class Command(BaseCommand):
    help = "Снимает TOP-статус с объявлений, у которых закончился срок продвижения"

    def handle(self, *args, **options):
        now = timezone.now()
        total = 0

        for Model in MODELS:
            count = Model.objects.filter(
                private_status=PrivateStatus.TOP,
                promoted_until__lt=now,
            ).update(private_status=PrivateStatus.COMMON, promoted_until=None)
            total += count

        if total:
            self.stdout.write(f"Сняли TOP-статус с {total} объявлений")