"""Incidents serializers and views."""

from rest_framework import generics, permissions, serializers

from .models import Incident


class IncidentSerializer(serializers.ModelSerializer):
    duration_seconds = serializers.ReadOnlyField()

    class Meta:
        model = Incident
        fields = [
            "id", "monitor", "started_at", "resolved_at", "is_resolved",
            "failure_count", "root_cause_error", "root_cause_message",
            "alert_sent", "resolved_alert_sent", "duration_seconds",
        ]
        read_only_fields = fields


class IncidentListView(generics.ListAPIView):
    """
    GET /api/v1/monitors/{monitor_id}/incidents/
    Lists incidents for a monitor, newest first.
    ?is_resolved=false → only open incidents.
    """

    serializer_class = IncidentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        from monitors.models import Monitor

        monitor_id = self.kwargs["monitor_id"]
        monitor = Monitor.objects.for_user(self.request.user).filter(pk=monitor_id).first()
        if not monitor:
            return Incident.objects.none()

        qs = Incident.objects.filter(monitor=monitor).order_by("-started_at")

        is_resolved = self.request.query_params.get("is_resolved")
        if is_resolved is not None:
            qs = qs.filter(is_resolved=is_resolved.lower() == "true")

        return qs
