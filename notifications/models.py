"""
Notification models.

Design decisions:

1. AlertChannel.config JSONField:
   - Stores channel-specific credentials/config (email address, Telegram chat_id, etc.).
   - Validated at serializer level using channel_type-specific validators.
   - In production, use FIELD_ENCRYPTION_KEY to encrypt sensitive values (bot_token).

2. MonitorAlert M2M table:
   - Explicit through table for future extensibility (e.g., per-monitor alert rules).
   - A user can configure multiple channels per monitor.

3. AlertChannel.channel_type choices:
   - EMAIL: {"email": "user@example.com"}
   - TELEGRAM: {"bot_token": "...", "chat_id": "123456789"}
   - SLACK: {"webhook_url": "https://hooks.slack.com/..."}
"""

from django.conf import settings
from django.db import models


class ChannelType(models.TextChoices):
    EMAIL = "email", "Email"
    TELEGRAM = "telegram", "Telegram"
    SLACK = "slack", "Slack"


class AlertChannel(models.Model):
    """
    A configured notification channel belonging to a user.
    Multiple monitors can use the same channel.
    """

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="alert_channels",
    )
    name = models.CharField(max_length=100)
    channel_type = models.CharField(max_length=20, choices=ChannelType.choices)
    # Stores channel-specific config dict — validated by serializer
    # Example: {"email": "ops@example.com"}
    #          {"bot_token": "...", "chat_id": "12345"}
    #          {"webhook_url": "https://hooks.slack.com/T.../..."}
    config = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "notifications_alertchannel"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["owner", "channel_type"], name="idx_channel_owner_type"),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.channel_type})"


class MonitorAlert(models.Model):
    """
    Connects a Monitor to an AlertChannel.
    When an incident opens or resolves, all connected active channels are notified.
    """

    monitor = models.ForeignKey(
        "monitors.Monitor",
        on_delete=models.CASCADE,
        related_name="alert_channels",
    )
    channel = models.ForeignKey(
        AlertChannel,
        on_delete=models.CASCADE,
        related_name="monitors",
    )

    class Meta:
        db_table = "notifications_monitoralert"
        unique_together = [("monitor", "channel")]

    def __str__(self) -> str:
        return f"{self.monitor.name} → {self.channel.name}"
