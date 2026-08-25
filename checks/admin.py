from django.contrib import admin
from .models import CheckResult, HourlyStats, DailyStats


@admin.register(CheckResult)
class CheckResultAdmin(admin.ModelAdmin):
    list_display = ["monitor", "checked_at", "status", "response_time_ms", "http_code", "error_type"]
    list_filter = ["status", "error_type"]
    search_fields = ["monitor__name", "monitor__url"]
    ordering = ["-checked_at"]
    readonly_fields = [f.name for f in CheckResult._meta.fields]


@admin.register(HourlyStats)
class HourlyStatsAdmin(admin.ModelAdmin):
    list_display = ["monitor", "hour", "uptime_pct", "avg_response_time_ms", "total_checks"]
    ordering = ["-hour"]


@admin.register(DailyStats)
class DailyStatsAdmin(admin.ModelAdmin):
    list_display = ["monitor", "date", "uptime_pct", "avg_response_time_ms", "incident_count"]
    ordering = ["-date"]
