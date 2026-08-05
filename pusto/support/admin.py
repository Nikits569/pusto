from django.contrib import admin
from django.utils.html import format_html
from .models import *
from django.utils import timezone

# ------------------- SupportTicketAdmin -------------------

@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ('id', 'subject', 'email', 'status', 'created_at', 'ip_address', 'user_agent')
    list_filter = ('status', 'created_at')
    ordering = ('-created_at',)
    list_editable = ('status',)

# ------------------- ClaimRequestAdmin -------------------

@admin.register(ClaimRequest)
class ClaimRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'target_link', 'reason', 'status', 'created_at', 'text')
    list_filter = ('status', 'created_at', 'reason')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)

    def target_link(self, obj):
        """Ссылка на объект жалобы (GenericForeignKey)"""
        if obj.target:
            return format_html(
                '<a href="/admin/{app}/{model}/{id}/change/" target="_blank">{title}</a>',
                app=obj.target._meta.app_label,
                model=obj.target._meta.model_name,
                id=obj.target.id,
                title=str(obj.target)
            )
        return "-"
    target_link.short_description = "Объект жалобы"

@admin.register(TrackedLink)
class TrackedLinkAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "slug", "original_url", "clicks", "created_at")
    search_fields = ("name", "slug", "original_url")