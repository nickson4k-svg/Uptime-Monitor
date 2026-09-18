"""
Monitors serializers.

Security:
- owner field is set from request.user (not from request body — prevents ownership hijacking).
- public_slug is read-only in the serializer (auto-generated on model save).
- validate_url: reject localhost/private IPs in production.
"""

import ipaddress
import socket
from urllib.parse import urlparse

from rest_framework import serializers

from .models import Monitor


class MonitorSerializer(serializers.ModelSerializer):
    owner = serializers.HiddenField(default=serializers.CurrentUserDefault())
    # Stats fields — read only, computed on serialization
    uptime_24h = serializers.SerializerMethodField()

    class Meta:
        model = Monitor
        fields = [
            "id",
            "owner",
            "name",
            "monitor_type",
            "url",
            "method",
            "expected_status_code",
            "interval",
            "timeout",
            "request_body",
            "request_headers",
            "regions",
            "quorum_threshold",
            "keyword",
            "keyword_should_exist",
            "tcp_port",
            "ssl_threshold_days",
            "domain_threshold_days",
            "current_status",
            "consecutive_failures",
            "failure_threshold",
            "last_checked_at",
            "is_active",
            "is_public",
            "public_slug",
            "created_at",
            "updated_at",
            "uptime_24h",
        ]
        read_only_fields = [
            "id",
            "current_status",
            "consecutive_failures",
            "last_checked_at",
            "public_slug",
            "created_at",
            "updated_at",
        ]

    def get_uptime_24h(self, obj) -> float | None:
        """Return uptime% for last 24 hours from annotated query or HourlyStats fallback."""
        if hasattr(obj, "uptime_24h_annotated"):
            val = obj.uptime_24h_annotated
            return float(round(val, 2)) if val is not None else None

        from datetime import timedelta

        from django.db.models import Avg
        from django.utils import timezone

        from checks.models import HourlyStats

        since = timezone.now() - timedelta(hours=24)
        result = HourlyStats.objects.filter(monitor=obj, hour__gte=since).aggregate(
            avg=Avg("uptime_pct")
        )

        val = result["avg"]
        return float(round(val, 2)) if val is not None else None

    def validate_url(self, value: str) -> str:
        """Block SSRF: reject private/loopback IPs in non-debug mode."""
        from django.conf import settings

        if settings.DEBUG:
            return value

        parsed = urlparse(value)
        host = parsed.hostname
        if not host:
            raise serializers.ValidationError("Invalid URL: no hostname.")

        try:
            ip = ipaddress.ip_address(socket.gethostbyname(host))
        except (socket.gaierror, ValueError):
            raise serializers.ValidationError(
                f"Cannot resolve hostname: {host}"
            ) from None

        if ip.is_private or ip.is_loopback or ip.is_link_local:
            raise serializers.ValidationError(
                "Private/internal URLs are not allowed for monitoring."
            )
        return value

    def validate_timeout(self, value: int) -> int:
        if value < 1 or value > 30:
            raise serializers.ValidationError(
                "Timeout must be between 1 and 30 seconds."
            )
        return value


class MonitorListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views — omits heavy fields."""

    uptime_24h = serializers.SerializerMethodField()

    class Meta:
        model = Monitor
        fields = [
            "id",
            "name",
            "monitor_type",
            "url",
            "method",
            "interval",
            "regions",
            "quorum_threshold",
            "current_status",
            "last_checked_at",
            "is_active",
            "is_public",
            "public_slug",
            "uptime_24h",
        ]

    def get_uptime_24h(self, obj) -> float | None:
        # Reuse the heavy method only when needed
        return MonitorSerializer.get_uptime_24h(self, obj)
