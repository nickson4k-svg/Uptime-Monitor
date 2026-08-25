from django.contrib import admin
from .models import Monitor


@admin.register(Monitor)
class MonitorAdmin(admin.ModelAdmin):
    list_display = ["name", "owner", "url", "current_status", "interval", "is_active", "last_checked_at"]
    list_filter = ["current_status", "is_active", "interval", "method"]
    search_fields = ["name", "url", "owner__email"]
    ordering = ["-created_at"]
    readonly_fields = ["public_slug", "consecutive_failures", "current_status", "last_checked_at"]
