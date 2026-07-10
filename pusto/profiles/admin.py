from django.contrib import admin
from .models import *


# Employer отдельно с полями IČO и компании
@admin.register(Employer)
class EmployerAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'ico', 'company_name', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('user__username', 'user__email', 'ico', 'company_name')
    readonly_fields = ('created_at',)

# Student
@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('created_at',)

# Common User
@admin.register(CommonUser)
class CommonUserAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('created_at',)