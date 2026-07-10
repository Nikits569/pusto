from django.db import models
from django.conf import settings
from django.core.validators import RegexValidator
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from datetime import timedelta


class Status(models.TextChoices):
    PROCESS = 'process', _('In progress')
    AGREE = 'agree', _('Approved')
    DENIED = 'denied', _('Denied')


# --------------------- VERIFICATION ---------------------

class Verification(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name=_('User')
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PROCESS,
        verbose_name=_('Status')
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Created at')
    )

    class Meta:
        verbose_name = _('Verification')
        verbose_name_plural = _('Verifications')


# --------------------- SUBCLASSES ---------------------

class Employer(Verification):
    ico_validator = RegexValidator(
        regex=r'^\d{8}$',
        message=_('ICO must consist of 8 digits')
    )
    ico = models.CharField(
        max_length=8,
        validators=[ico_validator],
        verbose_name=_('ICO')
    )
    company_name = models.CharField(
        max_length=150,
        verbose_name=_('Company name')
    )


class Student(Verification):
    pass


class CommonUser(Verification):
    pass


class TgLinkCode(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name=_('User')
    )
    code = models.CharField(
        max_length=10,
        unique=True,
        db_index=True,
        verbose_name=_('Code')
    )
    expires_at = models.DateTimeField(verbose_name=_('Expires at'))
    used = models.BooleanField(default=False, verbose_name=_('Used'))
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Created at')
    )

    class Meta:
        db_table = "tg_link_codes"
        ordering = ["-created_at"]
        verbose_name = _('Telegram link code')
        verbose_name_plural = _('Telegram link codes')

    def __str__(self):
        return f"TG link code for user {self.user_id}: {self.code}"

    @classmethod
    def create_code(cls, user, minutes_valid: int = 10):
        import random
        import string

        code = "".join(random.choices(string.digits, k=6))

        return cls.objects.create(
            user=user,
            code=code,
            expires_at=timezone.now() + timedelta(minutes=minutes_valid)
        )

    def is_valid(self) -> bool:
        return (not self.used) and self.expires_at > timezone.now()