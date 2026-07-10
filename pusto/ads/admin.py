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
)


# -----------------------------
# БАЗОВЫЕ СПРАВОЧНИКИ
# -----------------------------

@admin.register(Lifestyle)
class LifestyleAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)




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