from django.db import models
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.utils.translation import gettext_lazy as _


class Reason(models.TextChoices):
    OTHER = 'other', _('Other')
    SPAM = 'spam', _('Spam')
    SCAM = 'scam', _('Scam')
    FORBIDDEN = 'forbidden', _('Forbidden (18+)')
    FAKE = 'fake', _('Fake')
    TOXIC = 'toxic', _('Rude or offensive')
    CATFISHER = 'catfish', _('Impersonation')


class Status(models.TextChoices):
    PROCESS = 'process', _('In progress')
    AGREE = 'agree', _('Resolved')
    DENIED = 'denied', _('Denied')


class SupportTicket(models.Model):
    subject = models.CharField(max_length=200, verbose_name=_('Subject'))
    email = models.EmailField(max_length=200, blank=True, verbose_name=_('Email'))
    message = models.TextField(verbose_name=_('Message'))
    status = models.CharField(
        max_length=50,
        choices=Status.choices,
        default=Status.PROCESS,
        verbose_name=_('Status')
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Created at'))

    class Meta:
        verbose_name = _('Support ticket')
        verbose_name_plural = _('Support tickets')

    def __str__(self):
        return self.subject


class ClaimRequest(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='claim_requests',
        verbose_name=_('User')
    )
    reason = models.CharField(
        max_length=50,
        choices=Reason.choices,
        default=Reason.OTHER,
        verbose_name=_('Reason')
    )
    status = models.CharField(
        max_length=50,
        choices=Status.choices,
        default=Status.PROCESS,
        verbose_name=_('Status')
    )
    text = models.TextField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_('Description')
    )

    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        verbose_name=_('Content type')
    )
    object_id = models.PositiveIntegerField(verbose_name=_('Object ID'))
    target = GenericForeignKey('content_type', 'object_id')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Created at'))

    class Meta:
        verbose_name = _('Claim request')
        verbose_name_plural = _('Claim requests')
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'content_type', 'object_id'],
                name='unique_claim_per_user'
            )
        ]


class TrackedLink(models.Model):
    name = models.CharField(max_length=255, blank=True, verbose_name=_('Name'))
    original_url = models.URLField(verbose_name=_('Original URL'))
    slug = models.SlugField(unique=True, verbose_name=_('Slug'))
    clicks = models.PositiveIntegerField(default=0, verbose_name=_('Clicks'))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Created at'))

    class Meta:
        verbose_name = _('Tracked link')
        verbose_name_plural = _('Tracked links')

    def __str__(self):
        return self.name or self.original_url