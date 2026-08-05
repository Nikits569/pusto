from django.db import models
from datetime import timedelta
from ads.models import City, CaseTypeNeighbor, CaseTypeThing, Category


class notification(models.Model):

    created_at = models.DateTimeField(auto_now_add=True)

    email = models.EmailField(null=False, blank=False, verbose_name='email')
    # telegram = models.CharField(max_length=100 ,null=True, blank=True, verbose_name='telegram')

    city = models.CharField(max_length=100, choices=City.choices, default=City.BRATISLAVA, verbose_name='city')

    type = models.CharField(max_length=100, null=True, blank=True)


    # price = models.FloatField(null=True, blank=True, verbose_name='price')
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='category',
    )

    budget_from = models.IntegerField(null=True, blank=True, verbose_name='budget from')
    budget_to = models.IntegerField(null=True, blank=True, verbose_name='budget from')
    rooms = models.IntegerField(null=True, blank=True, verbose_name='rooms')

    last_checked_id = models.IntegerField(null=True, blank=True, verbose_name='last checked id')
