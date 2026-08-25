"""
Public status page — API and HTML view.

Access control:
- No JWT required — AllowAny.
- Only returns monitors where is_public=True AND public_slug matches.
- Never reveals the owner's identity or private monitors.
- 404 if slug not found OR monitor is not public.
"""

from django.shortcuts import get_object_or_404
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from monitors.models import Monitor


class PublicStatusAPIView(APIView):
    """
    GET /api/v1/public/status/<slug>/

    Returns monitor status without authentication.
    Used by the public status page frontend (JS fetch).
    """

    permission_classes = [AllowAny]
    authentication_classes = []  # No auth at all — no token lookup

    def get(self, request, slug: str):
        monitor = get_object_or_404(Monitor, public_slug=slug, is_public=True)

        # Recent check results (last 48 hours for the chart)
        from datetime import timedelta

        from django.utils import timezone

        from checks.models import CheckResult, HourlyStats
        from incidents.models import Incident

        now = timezone.now()
        recent_checks = CheckResult.objects.filter(
            monitor=monitor,
            checked_at__gte=now - timedelta(hours=1),
        ).values("status", "response_time_ms", "http_code", "checked_at")[:20]

        hourly_stats = HourlyStats.objects.filter(
            monitor=monitor,
            hour__gte=now - timedelta(hours=24),
        ).order_by("hour").values("hour", "uptime_pct", "avg_response_time_ms")

        open_incidents = Incident.objects.filter(
            monitor=monitor, is_resolved=False
        ).values("started_at", "root_cause_message", "failure_count")

        return Response(
            {
                "monitor": {
                    "id": monitor.pk,
                    "name": monitor.name,
                    "url": monitor.url,  # Optional: hide URL for privacy? Your choice.
                    "current_status": monitor.current_status,
                    "last_checked_at": monitor.last_checked_at,
                },
                "recent_checks": list(recent_checks),
                "hourly_stats": list(hourly_stats),
                "open_incidents": list(open_incidents),
            }
        )
