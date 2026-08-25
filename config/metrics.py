"""
Prometheus Metrics instrumentation for Pet-Uptime-Monitor.
"""

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from django.http import HttpResponse

# ── Metrics Definitions ────────────────────────────────────────────────────────

UPTIME_CHECKS_TOTAL = Counter(
    "uptime_checks_total",
    "Total monitor health check probes executed",
    ["monitor_type", "region", "status"],
)

UPTIME_CHECK_DURATION_SECONDS = Histogram(
    "uptime_check_duration_seconds",
    "Health check probe execution latency in seconds",
    ["monitor_type", "region"],
    buckets=(0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
)

UPTIME_ACTIVE_INCIDENTS = Gauge(
    "uptime_active_incidents",
    "Current count of active unresolved incidents",
)

UPTIME_MONITORS_TOTAL = Gauge(
    "uptime_monitors_total",
    "Total registered monitors",
    ["is_active"],
)


def update_gauge_metrics():
    """Sync dynamic gauges with database state."""
    try:
        from incidents.models import Incident
        from monitors.models import Monitor

        active_incidents = Incident.objects.filter(is_resolved=False).count()
        UPTIME_ACTIVE_INCIDENTS.set(active_incidents)

        active_monitors = Monitor.objects.filter(is_active=True).count()
        paused_monitors = Monitor.objects.filter(is_active=False).count()
        UPTIME_MONITORS_TOTAL.labels(is_active="true").set(active_monitors)
        UPTIME_MONITORS_TOTAL.labels(is_active="false").set(paused_monitors)
    except Exception:
        pass


def metrics_view(request):
    """
    Exposes Prometheus metrics at GET /metrics.
    """
    update_gauge_metrics()
    data = generate_latest()
    return HttpResponse(data, content_type=CONTENT_TYPE_LATEST)
