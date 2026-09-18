"""
Monitors views.

Multitenancy enforcement:
- get_queryset() always calls .for_user(request.user)
- Never use Monitor.objects.get(pk=...) directly in views — always through get_queryset()
- Returns 404 (not 403) for other users' monitors — prevents resource enumeration
"""

from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Monitor
from .permissions import IsOwner
from .serializers import MonitorListSerializer, MonitorSerializer


class MonitorViewSet(viewsets.ModelViewSet):
    """
    CRUD for monitors. All operations are scoped to request.user.

    Endpoints:
        GET    /api/v1/monitors/           — list user's monitors
        POST   /api/v1/monitors/           — create monitor
        GET    /api/v1/monitors/{id}/      — retrieve monitor
        PATCH  /api/v1/monitors/{id}/      — partial update
        DELETE /api/v1/monitors/{id}/      — delete monitor
        POST   /api/v1/monitors/{id}/pause/   — pause checking
        POST   /api/v1/monitors/{id}/resume/  — resume checking
        GET    /api/v1/monitors/{id}/stats/   — uptime + response time data
    """

    permission_classes = [permissions.IsAuthenticated, IsOwner]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        """
        CRITICAL: Always filter by owner.
        Uses Subquery annotation to eliminate N+1 queries for 24h uptime aggregation.
        """
        from datetime import timedelta

        from django.db.models import Avg, FloatField, OuterRef, Subquery
        from django.utils import timezone

        from checks.models import HourlyStats

        since = timezone.now() - timedelta(hours=24)
        uptime_subquery = (
            HourlyStats.objects.filter(
                monitor=OuterRef("pk"),
                hour__gte=since,
            )
            .values("monitor")
            .annotate(avg_uptime=Avg("uptime_pct"))
            .values("avg_uptime")[:1]
        )

        return (
            Monitor.objects.for_user(self.request.user)
            .annotate(
                uptime_24h_annotated=Subquery(
                    uptime_subquery, output_field=FloatField()
                )
            )
            .order_by("-created_at")
        )

    def get_serializer_class(self):
        if self.action == "list":
            return MonitorListSerializer
        return MonitorSerializer

    @action(detail=True, methods=["post"])
    def pause(self, request, pk=None):
        """POST /api/v1/monitors/{id}/pause/ — suspend checks without deleting."""
        monitor = self.get_object()
        if not monitor.is_active:
            return Response(
                {"detail": "Monitor is already paused."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        monitor.is_active = False
        monitor.current_status = "paused"
        monitor.save(update_fields=["is_active", "current_status"])
        return Response({"detail": "Monitor paused."})

    @action(detail=True, methods=["post"])
    def resume(self, request, pk=None):
        """POST /api/v1/monitors/{id}/resume/ — resume checks."""
        monitor = self.get_object()
        if monitor.is_active:
            return Response(
                {"detail": "Monitor is already active."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        monitor.is_active = True
        monitor.current_status = "unknown"
        monitor.consecutive_failures = 0
        monitor.save(
            update_fields=["is_active", "current_status", "consecutive_failures"]
        )
        return Response({"detail": "Monitor resumed."})

    @action(detail=True, methods=["get"])
    def stats(self, request, pk=None):
        """
        GET /api/v1/monitors/{id}/stats/?period=24h|7d|30d

        Returns uptime% and avg response time for each period bucket.
        Uses pre-aggregated HourlyStats/DailyStats — not raw CheckResult.
        """
        from datetime import timedelta

        from django.utils import timezone

        from checks.models import DailyStats, HourlyStats

        monitor = self.get_object()
        period = request.query_params.get("period", "24h")
        now = timezone.now()

        if period == "24h":
            since = now - timedelta(hours=24)
            qs = HourlyStats.objects.filter(monitor=monitor, hour__gte=since).order_by(
                "hour"
            )
            data = [
                {
                    "timestamp": row.hour.isoformat(),
                    "uptime_pct": float(row.uptime_pct) if row.uptime_pct else None,
                    "avg_response_time_ms": row.avg_response_time_ms,
                }
                for row in qs
            ]
        elif period in ("7d", "30d"):
            days = 7 if period == "7d" else 30
            since = (now - timedelta(days=days)).date()
            qs = DailyStats.objects.filter(monitor=monitor, date__gte=since).order_by(
                "date"
            )
            data = [
                {
                    "timestamp": row.date.isoformat(),
                    "uptime_pct": float(row.uptime_pct) if row.uptime_pct else None,
                    "avg_response_time_ms": row.avg_response_time_ms,
                }
                for row in qs
            ]
        else:
            return Response(
                {"error": "Invalid period. Use 24h, 7d, or 30d."}, status=400
            )

        return Response({"monitor_id": monitor.pk, "period": period, "data": data})
