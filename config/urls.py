"""
URL configuration for Pet Uptime Monitor.

Structure:
  /api/v1/          - Private REST API (JWT required)
  /api/v1/public/   - Public API (no auth — status pages)
  /api/schema/      - OpenAPI schema
  /ws/              - WebSocket (handled by ASGI routing)
  /status/<slug>/   - Public status page (rendered HTML)
  /admin/           - Django admin
"""

from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from config.health import health_live, health_ready
from config.metrics import metrics_view

urlpatterns = [
    # ─── Observability Probes & Metrics ───────────────────────────────────────
    path("health/live/", health_live, name="health-live"),
    path("health/ready/", health_ready, name="health-ready"),
    path("metrics", metrics_view, name="prometheus-metrics"),

    # ─── Django Admin ─────────────────────────────────────────────────────────
    path("admin/", admin.site.urls),

    # ─── API Schema ───────────────────────────────────────────────────────────
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path(
        "api/redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),


    # ─── Auth endpoints ───────────────────────────────────────────────────────
    path("api/v1/auth/", include("accounts.urls", namespace="accounts")),

    # ─── Private API (JWT required) ───────────────────────────────────────────
    path("api/v1/", include("monitors.urls", namespace="monitors")),
    path("api/v1/", include("checks.urls", namespace="checks")),
    path("api/v1/", include("incidents.urls", namespace="incidents")),
    path("api/v1/", include("notifications.urls", namespace="notifications")),

    # ─── Public API (no auth) ─────────────────────────────────────────────────
    path("api/v1/public/", include("monitors.public_urls", namespace="monitors-public")),

    # ─── Public status pages (rendered HTML) ──────────────────────────────────
    path("status/", include("monitors.status_urls", namespace="status")),

    # ─── Dashboard (serves HTML shell) ────────────────────────────────────────
    path("", include("dashboard.urls", namespace="dashboard")),
]

from django.conf import settings  # noqa: E402

if settings.DEBUG:
    try:
        import debug_toolbar  # noqa: F401

        urlpatterns.append(path("__debug__/", include("debug_toolbar.urls")))
    except ImportError:
        pass

