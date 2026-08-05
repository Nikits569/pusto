from django.contrib import admin
from .models import (
    Lifestyle,
    Category,
    NeighborPost,
    ThingsPost,
    JobPost,
    NeighborPostImage,
    ThingsPostImage,
    JobPostImage,
    advertisingBanner,
)
from django.contrib import admin
from modeltranslation.admin import TranslationAdmin
from django.utils import timezone
from django.utils.html import format_html

# -----------------------------
# БАЗОВЫЕ СПРАВОЧНИКИ
# -----------------------------


@admin.register(Lifestyle)
class LifestyleAdmin(TranslationAdmin):
    list_display = ('name',)

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "title_uk", "title_en", "title_sk", "is_active", "order")
    list_editable = ("is_active", "order")
    search_fields = ("title_uk", )
    list_filter = ("is_active",)

# -----------------------------
# INLINE IMAGES
# -----------------------------

class ThingsPostImageInline(admin.TabularInline):
    model = ThingsPostImage
    extra = 0


class JobPostImageInline(admin.TabularInline):
    model = JobPostImage
    extra = 0


class NeighborPostImageInline(admin.TabularInline):
    model = NeighborPostImage
    extra = 0


# -----------------------------
# ОБЩАЯ БАЗА ДЛЯ ПОСТОВ
# -----------------------------

class BasePostAdmin(admin.ModelAdmin):
    readonly_fields = (
        "created_at",
        "slug_title",
        "telegram_code",
    )
    list_per_page = 50
    save_on_top = True

    fieldsets = (
        ("Основное", {
            "fields": (
                "user",
                "title",
                "slug_title",
                "text",
                "city",
                "status",
                "private_status",
            )
        }),
        ("Контакты и верификация", {
            "fields": (
                "email",
                "email_confirmed",
                "email_token",
                "is_verified",
                #"phone",
                "withoutRegister",
            )
        }),
        ("source", {
            "fields": (
                "telegram_username",
                "telegram_id",
                "telegram_code",
                "chat_id",
                "message_id",
                "photo_id",
                "has_photo",
                "tg_deleted",

                "source",
                "link_facebook",
            )
        }),
        ("Служебное", {
            "fields": (
                "created_at",
                "created_ip",
                "preview_image",
            )
        }),
    )

    list_filter = (
        "status",
        "private_status",
        "is_verified",
        "email_confirmed",
        "source",
        "tg_deleted",
        "city",
        "withoutRegister",
        "created_at",
    )

    search_fields = (
        "id",
        "title",
        "text",
        "email",
        # "phone",
        "telegram_username",
        "telegram_id",
        "telegram_code",
        "chat_id",
        "message_id",
    )

    autocomplete_fields = ("user",)
    # date_hierarchy = "created_at"

# -----------------------------
# THINGS
# -----------------------------

@admin.register(ThingsPost)
class ThingsPostAdmin(BasePostAdmin):
    list_display = (
        "id",
        "title",
        "price",
        "city",
        "caseType",
        "condition",
        "category",
        "status",
        "private_status",
        "is_verified",
        "email_confirmed",
        "source",
        "has_photo",
        "created_at",
    )

    list_editable = (
        "status",
        "private_status",
        "is_verified",
        "email_confirmed",
    )

    list_filter = BasePostAdmin.list_filter + (
        "caseType",
        "condition",
        "category",
    )

    search_fields = BasePostAdmin.search_fields + (
        "category__slug",
        "category__title_sk",
        "category__title_uk",
    )

    autocomplete_fields = BasePostAdmin.autocomplete_fields + ("category",)
    inlines = [ThingsPostImageInline]

    fieldsets = BasePostAdmin.fieldsets[:1] + (
        ("Параметры товара", {
            "fields": (
                "caseType",
                "condition",
                "price",
                "category",
            )
        }),
    ) + BasePostAdmin.fieldsets[1:]


# -----------------------------
# JOBS
# -----------------------------

@admin.register(JobPost)
class JobPostAdmin(BasePostAdmin):
    list_display = (
        "id",
        "title",
        "company_name",
        "city",
        "caseType",
        "employment_type",
        "salary_from",
        "salary_to",
        "salary_period",
        "status",
        "private_status",
        "is_verified",
        "email_confirmed",
        "source",
        "has_photo",
        "created_at",
    )

    list_editable = (
        "status",
        "private_status",
        "is_verified",
        "email_confirmed",
    )

    list_filter = BasePostAdmin.list_filter + (
        "caseType",
        "employment_type",
        "salary_period",
    )

    search_fields = BasePostAdmin.search_fields + (
        "company_name",
    )

    inlines = [JobPostImageInline]

    fieldsets = BasePostAdmin.fieldsets[:1] + (
        ("Параметры вакансии", {
            "fields": (
                "caseType",
                "company_name",
                "employment_type",
                "salary_from",
                "salary_to",
                "salary_period",
            )
        }),
    ) + BasePostAdmin.fieldsets[1:]


# -----------------------------
# NEIGHBORS
# -----------------------------

@admin.register(NeighborPost)
class NeighborPostAdmin(BasePostAdmin):
    list_display = (
        "id",
        "title",
        "city",
        "caseType",
        "budget",
        "housing_type",
        "my_gender",
        "neighbor_gender",
        "count_neighbors",
        "status",
        "private_status",
        "is_verified",
        "email_confirmed",
        "source",
        "has_photo",
        "created_at",
        "rooms",
    )

    list_editable = (
        "status",
        "private_status",
        "is_verified",
        "email_confirmed",
    )

    list_filter = BasePostAdmin.list_filter + (
        "caseType",
        "housing_type",
        "rent_period",
        "my_gender",
        "neighbor_gender",
    )

    filter_horizontal = ("my_lifestyles", "neighbor_lifestyles")
    inlines = [NeighborPostImageInline]

    fieldsets = BasePostAdmin.fieldsets[:1] + (
        ("Параметры соседа / жилья", {
            "fields": (
                "caseType",
                "count_neighbors",
                "my_gender",
                "neighbor_gender",
                "my_age",
                "min_age",
                "max_age",
                "budget",
                "rent_period",
                "housing_type",
                "move_in_date",
                "my_lifestyles",
                "neighbor_lifestyles",
            )
        }),
    ) + BasePostAdmin.fieldsets[1:]


# -----------------------------
# IMAGES отдельно
# -----------------------------

@admin.register(ThingsPostImage)
class ThingsPostImageAdmin(admin.ModelAdmin):
    list_display = ("id", "post", "created_at")
    search_fields = ("post__title",)
    autocomplete_fields = ("post",)


@admin.register(JobPostImage)
class JobPostImageAdmin(admin.ModelAdmin):
    list_display = ("id", "post", "created_at")
    search_fields = ("post__title",)
    autocomplete_fields = ("post",)


@admin.register(NeighborPostImage)
class NeighborPostImageAdmin(admin.ModelAdmin):
    list_display = ("id", "post", "created_at")
    search_fields = ("post__title",)
    autocomplete_fields = ("post",)

@admin.register(advertisingBanner)
class AdvertisingBannerAdmin(admin.ModelAdmin):
    list_display = (
        'title_display',
        'status',
        'is_currently_active',
        'start_at',
        'end_at',
        'impressions_count',
        'clicks_count',
        'ctr_display',
        'preview_uk',
    )
    list_filter = ('status', 'start_at', 'end_at', 'created_at')
    search_fields = ('url', 'alt_uk', 'alt_en', 'alt_sk')
    readonly_fields = (
        'created_at',
        'impressions_count',
        'clicks_count',
        'ctr_display',
        'preview_uk',
        'preview_en',
        'preview_sk',
    )
    actions = ['make_active', 'make_closed', 'reset_stats']

    fieldsets = (
        ('Основне', {
            'fields': ('url', 'status', 'start_at', 'end_at', 'created_at')
        }),
        ('Українська', {
            'fields': ('image_uk', 'preview_uk', 'alt_uk')
        }),
        ('English', {
            'fields': ('image_en', 'preview_en', 'alt_en')
        }),
        ('Slovenčina', {
            'fields': ('image_sk', 'preview_sk', 'alt_sk')
        }),
        ('Статистика', {
            'fields': ('impressions_count', 'clicks_count', 'ctr_display')
        }),
    )

    def title_display(self, obj):
        return obj.alt_uk or obj.alt_en or obj.alt_sk or f'Banner #{obj.pk}'
    title_display.short_description = 'Назва'

    def is_currently_active(self, obj):
        now = timezone.now()
        active = obj.status == 'active'
        if obj.start_at and obj.start_at > now:
            active = False
        if obj.end_at and obj.end_at < now:
            active = False
        return active
    is_currently_active.boolean = True
    is_currently_active.short_description = 'Активний зараз'

    def ctr_display(self, obj):
        if not obj.impressions_count:
            return '—'
        clicks = obj.clicks_count or 0
        ctr = (clicks / obj.impressions_count) * 100
        return f'{ctr:.2f}%'
    ctr_display.short_description = 'CTR'

    def _preview(self, image_field):
        if not image_field:
            return '—'
        return format_html(
            '<img src="{}" style="max-height:80px; max-width:160px;" />',
            image_field.url,
        )

    def preview_uk(self, obj):
        return self._preview(obj.image_uk)
    preview_uk.short_description = 'Прев\'ю UK'

    def preview_en(self, obj):
        return self._preview(obj.image_en)
    preview_en.short_description = 'Preview EN'

    def preview_sk(self, obj):
        return self._preview(obj.image_sk)
    preview_sk.short_description = 'Náhľad SK'

    @admin.action(description='Активувати вибрані банери')
    def make_active(self, request, queryset):
        updated = queryset.update(status='active')
        self.message_user(request, f'Активовано банерів: {updated}')

    @admin.action(description='Закрити вибрані банери')
    def make_closed(self, request, queryset):
        updated = queryset.update(status='closed')
        self.message_user(request, f'Закрито банерів: {updated}')

    @admin.action(description='Скинути статистику показів/кліків')
    def reset_stats(self, request, queryset):
        updated = queryset.update(impressions_count=0, clicks_count=0)
        self.message_user(request, f'Скинуто статистику для: {updated}')