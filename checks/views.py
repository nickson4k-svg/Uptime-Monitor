"""Checks serializers and views."""

from rest_framework import generics, permissions
from rest_framework.response import Response

from .models import CheckResult


class CheckResultSerializer:
    pass  # defined inline below for brevity


from rest_framework import serializers


class CheckResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = CheckResult
        fields = [
            "id", "monitor", "checked_at", "status",
            "response_time_ms", "http_code", "error_type", "error_message",
        ]
        read_only_fields = fields


class CheckResultListView(generics.ListAPIView):
    """
    GET /api/v1/monitors/{monitor_id}/checks/
    Returns recent check results for a monitor owned by the current user.
    """

    serializer_class = CheckResultSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        from monitors.models import Monitor

        monitor_id = self.kwargs["monitor_id"]
        # Tenant-scoped: verify the monitor belongs to the user
        monitor = Monitor.objects.for_user(self.request.user).filter(pk=monitor_id).first()
        if not monitor:
            return CheckResult.objects.none()

        return CheckResult.objects.filter(monitor=monitor).order_by("-checked_at")[:100]
