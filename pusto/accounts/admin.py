from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import *


@admin.register(Profile)
class ProfileAdmin(UserAdmin):
    model = Profile
    list_display = (
        'email', 'first_name', 'last_name',
        'city', 'is_staff', 'is_active'
    )
    list_filter = ('is_staff', 'is_active', 'city')
    search_fields = ('email', 'first_name', 'last_name', 'city')
    ordering = ('email',)
    readonly_fields = ('created_at',)

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Личная информация', {
            'fields': ('first_name', 'last_name', 'city', 'avatar')
        }),
        ('Верификация', {
            'fields': ('verification_user', 'verification_email', 'verification_student', 'verification_employer')
        }),
        ('Права', {
            'fields': ('is_staff', 'is_active', 'is_superuser', 'user_permissions')
        }),
        ('Даты', {
            'fields': ('last_login', 'created_at')
        }),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'is_staff', 'is_active'),
        }),
    )