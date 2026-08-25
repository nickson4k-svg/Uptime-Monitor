from django.contrib import admin
from .models import AlertChannel, MonitorAlert


@admin.register(AlertChannel)
class AlertChannelAdmin(admin.ModelAdmin):
    list_display = ["name", "owner", "channel_type", "is_active"]
    list_filter = ["channel_type", "is_active"]
    search_fields = ["name", "owner__email"]


@admin.register(MonitorAlert)
class MonitorAlertAdmin(admin.ModelAdmin):
    list_display = ["monitor", "channel"]
    search_fields = ["monitor__name", "channel__name"]
