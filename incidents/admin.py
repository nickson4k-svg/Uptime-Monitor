from django.contrib import admin
from .models import Incident


@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_display = ["monitor", "started_at", "is_resolved", "failure_count", "alert_sent", "duration_seconds"]
    list_filter = ["is_resolved", "alert_sent"]
    search_fields = ["monitor__name"]
    ordering = ["-started_at"]
    readonly_fields = ["started_at", "duration_seconds"]
