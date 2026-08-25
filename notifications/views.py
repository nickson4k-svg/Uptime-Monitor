"""Notifications serializers and views."""

from rest_framework import permissions, serializers, viewsets

from .models import AlertChannel, ChannelType, MonitorAlert


# ─── Channel type-specific config validators ──────────────────────────────────

def validate_email_config(config: dict) -> None:
    if not config.get("email"):
        raise serializers.ValidationError({"config": "Email config requires 'email' key."})


def validate_telegram_config(config: dict) -> None:
    if not config.get("bot_token") or not config.get("chat_id"):
        raise serializers.ValidationError(
            {"config": "Telegram config requires 'bot_token' and 'chat_id'."}
        )


def validate_slack_config(config: dict) -> None:
    webhook = config.get("webhook_url", "")
    if not webhook.startswith("https://hooks.slack.com/"):
        raise serializers.ValidationError(
            {"config": "Slack config requires a valid 'webhook_url' starting with https://hooks.slack.com/."}
        )


CONFIG_VALIDATORS = {
    ChannelType.EMAIL: validate_email_config,
    ChannelType.TELEGRAM: validate_telegram_config,
    ChannelType.SLACK: validate_slack_config,
}


class AlertChannelSerializer(serializers.ModelSerializer):
    owner = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        model = AlertChannel
        fields = ["id", "owner", "name", "channel_type", "config", "is_active", "created_at"]
        read_only_fields = ["id", "created_at"]
        extra_kwargs = {
            # Sensitive: write-only to avoid leaking tokens in GET responses
            "config": {"write_only": False},
        }

    def validate(self, attrs):
        channel_type = attrs.get("channel_type") or (self.instance and self.instance.channel_type)
        config = attrs.get("config") or {}
        validator = CONFIG_VALIDATORS.get(channel_type)
        if validator:
            validator(config)
        return attrs


class MonitorAlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = MonitorAlert
        fields = ["id", "monitor", "channel"]

    def validate(self, attrs):
        user = self.context["request"].user
        # Ensure both monitor and channel belong to the same user
        if attrs["monitor"].owner != user:
            raise serializers.ValidationError("Monitor does not belong to you.")
        if attrs["channel"].owner != user:
            raise serializers.ValidationError("Alert channel does not belong to you.")
        return attrs


class AlertChannelViewSet(viewsets.ModelViewSet):
    """CRUD for alert channels, scoped to request.user."""

    serializer_class = AlertChannelSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return AlertChannel.objects.filter(owner=self.request.user).order_by("name")


class MonitorAlertViewSet(viewsets.ModelViewSet):
    """Link monitors to alert channels."""

    serializer_class = MonitorAlertSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_queryset(self):
        return MonitorAlert.objects.filter(
            monitor__owner=self.request.user
        ).select_related("monitor", "channel")
