from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import *

@receiver(post_save, sender=ThingsPost)
def calculate_score(sender, instance, created, **kwargs):
    if not created:
        return

    score = 0

    if instance.source == "pusto":
        score += 100

    elif instance.source == "telegram":
        score += 50

    elif instance.source == "bazos":
        score += 20

    if instance.has_photo or instance.img_bazos:
        score += 20

    if instance.category:
        score += 20

    if instance.price:
        score += 20

    ThingsPost.objects.filter(pk=instance.pk).update(score=score)