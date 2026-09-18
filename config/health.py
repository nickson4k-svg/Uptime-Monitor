"""
Kubernetes Health Probes — Liveness and Readiness checks.
"""

import logging

from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse

logger = logging.getLogger(__name__)


def health_live(request):
    """
    Liveness probe: verifies the ASGI/WSGI web application process is responsive.
    Returns HTTP 200 immediately.
    """
    return JsonResponse({"status": "ok", "service": "pet-uptime-monitor"})


def health_ready(request):
    """
    Readiness probe: validates critical dependencies (Database, Redis/Cache).
    Returns HTTP 200 if all dependencies are healthy, or HTTP 503 if any are degraded.
    """
    checks = {}
    is_healthy = True

    # 1. Database Check
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        checks["database"] = "ok"
    except Exception as e:
        logger.error("Readiness check failed for database: %s", e)
        checks["database"] = f"error: {str(e)[:100]}"
        is_healthy = False

    # 2. Cache / Redis Check
    try:
        cache.set("_health_probe", "ok", timeout=5)
        val = cache.get("_health_probe")
        if val == "ok":
            checks["cache"] = "ok"
        else:
            checks["cache"] = "degraded"
            is_healthy = False
    except Exception as e:
        logger.error("Readiness check failed for cache: %s", e)
        checks["cache"] = f"error: {str(e)[:100]}"
        is_healthy = False

    status_code = 200 if is_healthy else 503
    return JsonResponse(
        {
            "status": "ready" if is_healthy else "unhealthy",
            "checks": checks,
        },
        status=status_code,
    )
