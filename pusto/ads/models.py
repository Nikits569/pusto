from django.db import models
from django.conf import settings
import uuid
from django.utils.text import slugify
from unidecode import unidecode
from django.utils.crypto import get_random_string
from django.utils import timezone
from django.contrib.postgres.operations import TrigramExtension
from django.db import migrations
from django.utils.translation import gettext_lazy as _


class Migration(migrations.Migration):
    dependencies = []

    operations = [
        TrigramExtension(),
    ]


def generate_unique_telegram_code(model_class):
    """Генерирует уникальный 12-символьный код для модели."""
    code = str(uuid.uuid4()).replace("-", "")[:12]
    while model_class.objects.filter(telegram_code=code).exists():
        code = str(uuid.uuid4()).replace("-", "")[:12]
    return code


def generate_unique_slug(model_class, value, instance=None, field_name="slug", filter_kwargs=None):
    base_slug = slugify(unidecode(value))[:60] or "item"
    slug = base_slug
    counter = 2

    qs = model_class.objects.all()

    if filter_kwargs:
        qs = qs.filter(**filter_kwargs)

    if instance and instance.pk:
        qs = qs.exclude(pk=instance.pk)

    while qs.filter(**{field_name: slug}).exists():
        suffix = f"-{counter}"
        slug = f"{base_slug[:60 - len(suffix)]}{suffix}"
        counter += 1

    return slug


class Gender(models.IntegerChoices):
    ANY = 0, _('невизначана стать')
    MALE = 1, _('чоловічий')
    FEMALE = 2, _('жіночий')


class HousingType(models.TextChoices):
    ANY = 'any', _('будь-яке житло')
    ROOM = 'room', _('кімнату')
    APARTMENT = 'apartment', _('квартиру')
    DORM = 'dorm', _('гуртожиток')


class RentPeriod(models.TextChoices):
    ANY = 'any', _('будь який період')
    DAY = 'day', _('день')
    WEEK = 'week', _('неділю')
    MONTH = 'month', _('місяць')
    YEAR = 'year', _('рік')


class Lifestyle(models.Model):
    name = models.CharField(max_length=50, unique=True, verbose_name=_('Name'))

    def __str__(self):
        return self.name


class Condition(models.TextChoices):
    NEW = 'new', _('нове')
    USED = 'used', _('б/У')


class City(models.TextChoices):
    #ANY = 'any', _('Будь-яке місто')

    KOSICE = 'Kosice', _('Кошиця')
    PRESOV = 'Presov', _('Прешов')
    BRATISLAVA = 'Bratislava', _('Братислава')
    TRNAVA = 'Trnava', _('Трнава')
    ZILINA = 'Zilina', _('Жиліна')
    NITRA = 'Nitra', _('Нітра')
    TRENCIN = 'Trencin', _('Тренчин')
    BANSKA_BISTRICA = 'Banska-bristrica', _('Банска-Бистрица')
    POPRAD = 'Poprad', _('Попрад')


class StatusAdv(models.TextChoices):
    ACTIVE = 'active', _('Active')
    PENDING = 'pending', _('Pending')
    CLOSED = 'closed', _('Closed')


class PrivateStatus(models.TextChoices):
    COMMON = 'common', _('Common')
    TOP = 'top', _('Top')


class CaseTypeThing(models.TextChoices):
    FORADMIN = 'forAdmin', _('For admin')
    SELL = 'sell_category', _('продаж')
    BUY = 'buy_category', _('купівля')
    FREE = 'free_category', _('безскоштовно')


class CaseTypeJob(models.TextChoices):
    FORADMIN = 'forAdmin', _('For admin')
    FIND = 'findJob', _('Looking for a job')
    GIVE = 'giveJob', _('Offering a job')


class CaseTypeNeighbor(models.TextChoices):
    FORADMIN = 'forAdmin', _('For admin')
    FIND_ROOMMATE = 'findNeighbor', _('шукаю сусіда')
    RENT = 'rent', _('оренда')

class Category(models.Model):
    slug = models.SlugField(max_length=60, unique=True, blank=True, verbose_name=_('Slug'))
    is_active = models.BooleanField(default=True, verbose_name=_('Is active'))
    order = models.PositiveIntegerField(default=0, verbose_name=_('Order'))

    # названия по языкам

    title_uk = models.CharField(max_length=120, verbose_name=_('Title'))
    title_en = models.CharField(max_length=120, null=True, blank=True, verbose_name=_('Title_en'))
    title_sk = models.CharField(max_length=120, null=True, blank=True, verbose_name=_('Title sk'))
    class Meta:
        ordering = ["order", "id"]
        verbose_name = _('Category')
        verbose_name_plural = _('Categories')

    def __str__(self):
        return self.title_uk

    def save(self, *args, **kwargs):
        if not self.slug:
            source_title = self.title_uk
            self.slug = generate_unique_slug(
                model_class=Category,
                value=source_title,
                instance=self,
            )
        super().save(*args, **kwargs)



class EmploymentType(models.TextChoices):
    ANY = 'any', _('Any')
    FULL_TIME = 'full', _('Full-time')
    PART_TIME = 'part', _('Part-time')
    CONTRACT = 'contract', _('Contract')
    TEMP = 'temp', _('Temporary')
    INTERNSHIP = 'intern', _('Internship')


class SalaryPeriod(models.TextChoices):
    HOUR = 'hour', _('Per hour')
    MONTH = 'month', _('Per month')
    DAY = 'day', _('Per day')
    WEEK = 'week', _('Per week')


# --------------------- POSTS ---------------------

class ThingsPost(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='things_posts',
        verbose_name=_('User'),
    )
    telegram_username = models.CharField(max_length=100, blank=True, verbose_name=_('Telegram username'))
    telegram_id = models.BigIntegerField(null=True, blank=True, db_index=True, verbose_name=_('Telegram ID'))
    created_ip = models.GenericIPAddressField(null=True, blank=True, verbose_name=_('Created IP'))

    created_at = models.DateTimeField(default=timezone.now, verbose_name=_('Created at'))
    title = models.CharField(max_length=100, verbose_name=_('Title'))
    slug_title = models.SlugField(max_length=120, blank=True, verbose_name=_('Slug title'))
    text = models.TextField(blank=True, verbose_name=_('Text'))

    title_en = models.CharField(blank=True, null=True, max_length=150, verbose_name=_('Title_en'))
    text_en = models.TextField(blank=True, null=True, verbose_name=_('Text_en'))

    title_sk = models.CharField(blank=True, null=True, max_length=150, verbose_name=_('Title_sk'))
    text_sk = models.TextField(blank=True, null=True, verbose_name=_('Text_sk'))

    city = models.CharField(max_length=20, choices=City.choices, verbose_name=_('City'))

    #source_telegram = models.BooleanField(null=True, blank=True, default=None, verbose_name=_('Source Telegram'))
    #source_facebook = models.BooleanField(null=True, blank=True, default=None, verbose_name=_('Source Facebook'))
    #source_bazos = models.BooleanField(null=True, blank=True, default=None, verbose_name=_('Source Bazos'))

    source = models.CharField(blank=True, null=True, max_length=150, verbose_name=_('Source'))

    link_bazos =  models.CharField(max_length=1000, null=True, blank=True, default=None, verbose_name=_('Link Bazos'))
    id_bazos = models.BigIntegerField(null=True, blank=True, default=None, verbose_name=_('Bazos ID'))
    img_bazos = models.CharField(max_length=1000, null=True, blank=True, default=None, verbose_name=_('Image Bazos'))

    link_facebook = models.CharField(max_length=1000, null=True, blank=True, verbose_name=_('Facebook link'))
    # phone = models.CharField(max_length=20, blank=True)
    caseType = models.CharField(
        max_length=50,
        choices=CaseTypeThing.choices,
        blank=True,
        null=True,
        verbose_name=_('Case type'),
    )

    chat_id = models.CharField(max_length=100, blank=True, verbose_name=_('Chat ID'))
    message_id = models.CharField(max_length=100, null=True, blank=True, verbose_name=_('Message ID'))
    photo_id = models.CharField(max_length=100, null=True, blank=True, verbose_name=_('Photo ID'))
    has_photo = models.BooleanField(null=True, blank=True, default=None, verbose_name=_('Has photo'))
    telegram_code = models.CharField(max_length=12, unique=True, blank=True, null=True, verbose_name=_('Telegram code'))
    tg_deleted = models.BooleanField(default=False, verbose_name=_('Telegram deleted'))

    condition = models.CharField(
        max_length=25,
        choices=Condition.choices,
        blank=True,
        null=True,
        verbose_name=_('Condition'),
    )
    price = models.IntegerField(null=True, blank=True, verbose_name=_('Price'))
    email = models.EmailField(verbose_name=_('Email'))
    is_verified = models.BooleanField(default=False, verbose_name=_('Is verified'))

    email_token = models.CharField(max_length=64, unique=True, null=True, blank=True, verbose_name=_('Email token'))
    email_confirmed = models.BooleanField(default=False, verbose_name=_('Email confirmed'))
    status = models.CharField(
        max_length=20,
        choices=StatusAdv.choices,
        default=StatusAdv.PENDING,
        verbose_name=_('Status'),
    )

    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="things",
        null=True,
        blank=True,
        db_column='productCategory',
        verbose_name=_('Category'),
    )

    private_status = models.CharField(
        max_length=50,
        choices=PrivateStatus.choices,
        default=PrivateStatus.COMMON,
        verbose_name=_('Private status'),
    )
    promoted_until = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Promoted until'),
    )

    withoutRegister = models.BooleanField(default=False, verbose_name=_('Without registration'))

    preview_image = models.CharField(max_length=250, null=True, blank=True, verbose_name=_('Preview image'))

    def save(self, *args, **kwargs):
        if not self.slug_title and self.title:
            self.slug_title = slugify(unidecode(self.title))

        #if self.source_telegram and not self.telegram_code:
        #    self.telegram_code = generate_unique_telegram_code(ThingsPost)

        super().save(*args, **kwargs)

    @property
    def created_at_local(self):
        return timezone.localtime(self.created_at)

    class Meta:
        verbose_name = _('Things post')
        verbose_name_plural = _('Things posts')


class NeighborPost(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='neighbor_posts',
        verbose_name=_('User'),
    )
    telegram_username = models.CharField(max_length=100, blank=True, verbose_name=_('Telegram username'))
    telegram_id = models.BigIntegerField(null=True, blank=True, db_index=True, verbose_name=_('Telegram ID'))
    created_ip = models.GenericIPAddressField(null=True, blank=True, verbose_name=_('Created IP'))

    created_at = models.DateTimeField(default=timezone.now, verbose_name=_('Created at'))
    title = models.CharField(max_length=150, verbose_name=_('Title'))
    slug_title = models.SlugField(max_length=120, blank=True, verbose_name=_('Slug title'))
    text = models.TextField(blank=True, verbose_name=_('Text'))

    title_en = models.CharField(blank=True, null=True, max_length=150, verbose_name=_('Title_en'))
    text_en = models.TextField(blank=True, null=True, verbose_name=_('Text_en'))

    title_sk = models.CharField(blank=True, null=True, max_length=150, verbose_name=_('Title_sk'))
    text_sk = models.TextField(blank=True, null=True, verbose_name=_('Text_sk'))

    city = models.CharField(max_length=20, choices=City.choices, verbose_name=_('City'))
    source = models.CharField(blank=True, null=True, max_length=150, verbose_name=_('Source'))
    #source_bazos = models.BooleanField(null=True, blank=True, default=None, verbose_name=_('Source Bazos'))
    #source_telegram = models.BooleanField(null=True, blank=True, default=None, verbose_name=_('Source Telegram'))
    #source_facebook = models.BooleanField(null=True, blank=True, default=None, verbose_name=_('Source Facebook'))

    deposit = models.CharField(blank=True, null=True, max_length=150, verbose_name=_('Deposit'))

    link_facebook = models.CharField(max_length=1000, null=True, blank=True, verbose_name=_('Facebook link'))
    # phone = models.CharField(max_length=20, blank=True)
    caseType = models.CharField(
        max_length=30,
        choices=CaseTypeNeighbor.choices,
        blank=True,
        null=True,
        verbose_name=_('Case type'),
    )
    telegram_code = models.CharField(max_length=12, unique=True, blank=True, null=True, verbose_name=_('Telegram code'))
    tg_deleted = models.BooleanField(default=False, verbose_name=_('Telegram deleted'))


    link_bazos =  models.CharField(max_length=1000, null=True, blank=True, default=None, verbose_name=_('Link Bazos'))
    id_bazos = models.BigIntegerField(null=True, blank=True, default=None, verbose_name=_('Bazos ID'))
    img_bazos = models.CharField(max_length=1000, null=True, blank=True, default=None, verbose_name=_('Image Bazos'))

    chat_id = models.CharField(max_length=100, blank=True, verbose_name=_('Chat ID'))
    message_id = models.CharField(max_length=100, null=True, blank=True, verbose_name=_('Message ID'))
    photo_id = models.CharField(max_length=100, null=True, blank=True, verbose_name=_('Photo ID'))
    has_photo = models.BooleanField(null=True, blank=True, default=None, verbose_name=_('Has photo'))

    count_neighbors = models.IntegerField(null=True, blank=True, default=None, verbose_name=_('Number of neighbors'))
    my_gender = models.IntegerField(choices=Gender.choices, default=Gender.ANY, verbose_name=_('My gender'))
    neighbor_gender = models.IntegerField(
        choices=Gender.choices,
        default=Gender.ANY,
        verbose_name=_('Neighbor gender'),
    )
    my_age = models.PositiveSmallIntegerField(null=True, blank=True, default=16, verbose_name=_('My age'))
    min_age = models.PositiveSmallIntegerField(null=True, blank=True, default=16, verbose_name=_('Minimum age'))
    max_age = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name=_('Maximum age'))
    budget = models.PositiveIntegerField(null=True, blank=True, verbose_name=_('Budget'))

    rooms = models.FloatField(null=True, blank=True, verbose_name=_('Rooms'))

    rent_period = models.CharField(
        max_length=50,
        choices=RentPeriod.choices,
        default=RentPeriod.ANY,
        verbose_name=_('Rent period'),
    )
    my_lifestyles = models.ManyToManyField(
        Lifestyle,
        related_name='my_posts',
        blank=True,
        verbose_name=_('My lifestyles'),
    )
    neighbor_lifestyles = models.ManyToManyField(
        Lifestyle,
        related_name='neighbor_posts',
        blank=True,
        verbose_name=_('Neighbor lifestyles'),
    )
    housing_type = models.CharField(
        max_length=20,
        choices=HousingType.choices,
        default=HousingType.ANY,
        verbose_name=_('Housing type'),
    )
    move_in_date = models.DateField(null=True, blank=True, verbose_name=_('Move-in date'))
    email = models.EmailField(verbose_name=_('Email'))
    is_verified = models.BooleanField(default=False, verbose_name=_('Is verified'))

    email_token = models.CharField(max_length=64, unique=True, null=True, blank=True, verbose_name=_('Email token'))
    email_confirmed = models.BooleanField(default=False, verbose_name=_('Email confirmed'))
    status = models.CharField(
        max_length=20,
        choices=StatusAdv.choices,
        default=StatusAdv.PENDING,
        verbose_name=_('Status'),
    )

    private_status = models.CharField(
        max_length=50,
        choices=PrivateStatus.choices,
        default=PrivateStatus.COMMON,
        verbose_name=_('Private status'),
    )
    promoted_until = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Promoted until'),
    )

    withoutRegister = models.BooleanField(default=False, verbose_name=_('Without registration'))

    preview_image = models.CharField(max_length=250, null=True, blank=True, verbose_name=_('Preview image'))

    ad_id = models.CharField(max_length=100, null=True, blank=True, verbose_name=_('Ad ID'))
    def __str__(self):
        return f'{self.city} — {self.user}'

    def save(self, *args, **kwargs):
        if not self.slug_title and self.title:
            self.slug_title = slugify(unidecode(self.title))

        #if self.source_telegram and not self.telegram_code:
        #    self.telegram_code = generate_unique_telegram_code(NeighborPost)
        super().save(*args, **kwargs)

    @property
    def created_at_local(self):
        return timezone.localtime(self.created_at)

    class Meta:
        verbose_name = _('Neighbor post')
        verbose_name_plural = _('Neighbor posts')


class JobPost(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='jobs_posts',
        verbose_name=_('User'),
    )
    telegram_username = models.CharField(max_length=100, blank=True, verbose_name=_('Telegram username'))
    telegram_id = models.BigIntegerField(null=True, blank=True, db_index=True, verbose_name=_('Telegram ID'))
    created_ip = models.GenericIPAddressField(null=True, blank=True, verbose_name=_('Created IP'))

    created_at = models.DateTimeField(default=timezone.now, verbose_name=_('Created at'))
    title = models.CharField(max_length=150, verbose_name=_('Title'))
    slug_title = models.SlugField(max_length=120, blank=True, verbose_name=_('Slug title'))
    text = models.TextField(blank=True, verbose_name=_('Text'))

    title_en = models.CharField(blank=True, null=True, max_length=150, verbose_name=_('Title_en'))
    text_en = models.TextField(blank=True, null=True, verbose_name=_('Text_en'))

    city = models.CharField(max_length=20, choices=City.choices, verbose_name=_('City'))
    #source_telegram = models.BooleanField(null=True, blank=True, default=None, verbose_name=_('Source Telegram'))
    #source_facebook = models.BooleanField(null=True, blank=True, default=None, verbose_name=_('Source Facebook'))

    source = models.CharField(blank=True, null=True, max_length=150, verbose_name=_('Source'))
    link_facebook = models.CharField(max_length=1000, null=True, blank=True, verbose_name=_('Facebook link'))
    # phone = models.CharField(max_length=20, blank=True)
    caseType = models.CharField(
        max_length=15,
        choices=CaseTypeJob.choices,
        blank=True,
        null=True,
        verbose_name=_('Case type'),
    )

    chat_id = models.CharField(max_length=100, blank=True, verbose_name=_('Chat ID'))
    message_id = models.CharField(max_length=100, null=True, blank=True, verbose_name=_('Message ID'))
    photo_id = models.CharField(max_length=100, null=True, blank=True, verbose_name=_('Photo ID'))
    has_photo = models.BooleanField(null=True, blank=True, default=None, verbose_name=_('Has photo'))
    telegram_code = models.CharField(max_length=12, unique=True, blank=True, null=True, verbose_name=_('Telegram code'))
    tg_deleted = models.BooleanField(default=False, verbose_name=_('Telegram deleted'))

    employment_type = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        choices=EmploymentType.choices,
        default=EmploymentType.ANY,
        verbose_name=_('Employment type'),
    )
    salary_from = models.PositiveIntegerField(null=True, blank=True, verbose_name=_('Salary from'))
    salary_to = models.PositiveIntegerField(null=True, blank=True, verbose_name=_('Salary to'))
    salary_period = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        choices=SalaryPeriod.choices,
        default=SalaryPeriod.MONTH,
        verbose_name=_('Salary period'),
    )
    email = models.EmailField(verbose_name=_('Email'))
    is_verified = models.BooleanField(default=False, verbose_name=_('Is verified'))

    email_token = models.CharField(max_length=64, unique=True, null=True, blank=True, verbose_name=_('Email token'))
    email_confirmed = models.BooleanField(default=False, verbose_name=_('Email confirmed'))
    status = models.CharField(
        max_length=20,
        choices=StatusAdv.choices,
        default=StatusAdv.PENDING,
        verbose_name=_('Status'),
    )

    company_name = models.CharField(max_length=150, blank=True, verbose_name=_('Company name'))
    private_status = models.CharField(
        max_length=50,
        choices=PrivateStatus.choices,
        default=PrivateStatus.COMMON,
        verbose_name=_('Private status'),
    )
    promoted_until = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Promoted until'),
    )

    withoutRegister = models.BooleanField(default=False, verbose_name=_('Without registration'))

    preview_image = models.CharField(max_length=250, null=True, blank=True, verbose_name=_('Preview image'))

    def save(self, *args, **kwargs):
        if not self.slug_title and self.title:
            self.slug_title = slugify(unidecode(self.title))

        # if self.source_telegram and not self.telegram_code:
        #     self.telegram_code = generate_unique_telegram_code(JobPost)
        super().save(*args, **kwargs)

    @property
    def created_at_local(self):
        return timezone.localtime(self.created_at)

    class Meta:
        verbose_name = _('Job post')
        verbose_name_plural = _('Job posts')


class JobPostImage(models.Model):
    post = models.ForeignKey(JobPost, on_delete=models.CASCADE, related_name='images', verbose_name=_('Post'))
    image = models.ImageField(upload_to='job/', verbose_name=_('Image'))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Created at'))

    class Meta:
        verbose_name = _('Job post image')
        verbose_name_plural = _('Job post images')


class ThingsPostImage(models.Model):
    post = models.ForeignKey(ThingsPost, on_delete=models.CASCADE, related_name='images', verbose_name=_('Post'))
    image = models.ImageField(upload_to='things/', verbose_name=_('Image'))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Created at'))

    class Meta:
        verbose_name = _('Things post image')
        verbose_name_plural = _('Things post images')


class NeighborPostImage(models.Model):
    post = models.ForeignKey(NeighborPost, on_delete=models.CASCADE, related_name='images', verbose_name=_('Post'))
    image = models.ImageField(upload_to='neighbor/', verbose_name=_('Image'))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Created at'))

    class Meta:
        verbose_name = _('Neighbor post image')
        verbose_name_plural = _('Neighbor post images')