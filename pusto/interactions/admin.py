from django.contrib import admin
from .models import *

# Student
@admin.register(notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'email', 'city', 'type', 'category', 'budget_from', 'budget_to', 'rooms', 'last_checked_id')
    search_fields = ('created_at', 'email', 'city', 'type')