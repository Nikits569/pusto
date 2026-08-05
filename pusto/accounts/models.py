from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils.translation import gettext_lazy as _
import uuid


class VerificationEmailStatus(models.TextChoices):
    UNVERIFIED = 'unverified', _('Unverified')
    VERIFIED_EMAIL = 'verified_email', _('Verified')


class ProfileManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError(_('Email is required'))
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))

        return self.create_user(email, password, **extra_fields)


class Profile(AbstractBaseUser, PermissionsMixin):
    CITY_CHOICES = [
        ('bratislava', _('Bratislava')),
        ('kosice', _('Kosice')),
        ('trnava', _('Trnava')),
        ('presov', _('Presov')),
    ]

    email = models.EmailField(unique=True, verbose_name=_('Email'))
    first_name = models.CharField(max_length=50, blank=True, verbose_name=_('First name'))
    last_name = models.CharField(max_length=50, blank=True, verbose_name=_('Last name'))
    telegram_id = models.BigIntegerField(unique=True, null=True, blank=True, verbose_name=_('Telegram ID'))

    city = models.CharField(
        max_length=50,
        choices=CITY_CHOICES,
        blank=True,
        verbose_name=_('City')
    )

    avatar = models.ImageField(
        upload_to='avatars/',
        blank=True,
        null=True,
        verbose_name=_('Avatar')
    )

    verification_user = models.BooleanField(default=False, verbose_name=_('Verified user'))
    verification_email = models.BooleanField(default=False, verbose_name=_('Email verified'))
    verification_student = models.BooleanField(default=False, verbose_name=_('Student verified'))
    verification_employer = models.BooleanField(default=False, verbose_name=_('Employer verified'))

    # email_verified = models.CharField(
    #     max_length=30,
    #     choices=VerificationEmailStatus.choices,
    #     default=VerificationEmailStatus.UNVERIFIED
    # )

    email_verification_token = models.CharField(
        max_length=36,
        default=uuid.uuid4,
        editable=False,
        unique=True,
        verbose_name=_('Email verification token')
    )

    is_active = models.BooleanField(default=False, verbose_name=_('Is active'))
    is_staff = models.BooleanField(default=False, verbose_name=_('Is staff'))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Created at'))

    objects = ProfileManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    groups = models.ManyToManyField(
        'auth.Group',
        related_name='profile_set',
        blank=True,
        help_text=_('Groups this user belongs to'),
        verbose_name=_('Groups')
    )

    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='profile_set',
        blank=True,
        help_text=_('Specific permissions for this user'),
        verbose_name=_('Permissions')
    )

    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True)

    def __str__(self):
        return self.email

    class Meta:
        verbose_name = _('Profile')
        verbose_name_plural = _('Profiles')