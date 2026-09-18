"""
Unit tests for Observability: Health probes, Prometheus metrics, Request-ID, and JSON logging.
"""

import json
import logging

import pytest
from django.test import RequestFactory

from config.health import health_live, health_ready
from config.logging import StructuredJSONFormatter
from config.metrics import metrics_view
from config.middleware import RequestIDMiddleware, get_current_request_id


@pytest.mark.unit
class TestHealthProbes:
    def test_liveness_probe_returns_200(self, rf: RequestFactory):
        request = rf.get("/health/live/")
        response = health_live(request)
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data["status"] == "ok"
        assert data["service"] == "pet-uptime-monitor"

    @pytest.mark.django_db
    def test_readiness_probe_healthy_returns_200(self, rf: RequestFactory):
        request = rf.get("/health/ready/")
        response = health_ready(request)
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data["status"] == "ready"
        assert data["checks"]["database"] == "ok"
        assert data["checks"]["cache"] == "ok"


@pytest.mark.django_db
class TestPrometheusMetrics:
    def test_metrics_endpoint_returns_prometheus_format(
        self, rf: RequestFactory, monitor
    ):
        request = rf.get("/metrics")
        response = metrics_view(request)
        assert response.status_code == 200
        content = response.content.decode("utf-8")
        assert "uptime_checks_total" in content
        assert "uptime_check_duration_seconds" in content
        assert "uptime_active_incidents" in content
        assert "uptime_monitors_total" in content


@pytest.mark.unit
class TestRequestIDMiddleware:
    def test_middleware_generates_request_id_if_missing(self, rf: RequestFactory):
        def dummy_view(req):
            assert hasattr(req, "id")
            assert get_current_request_id() == req.id
            from django.http import HttpResponse

            return HttpResponse("OK")

        middleware = RequestIDMiddleware(dummy_view)
        request = rf.get("/api/v1/monitors/")
        response = middleware(request)

        assert response.status_code == 200
        assert "X-Request-ID" in response.headers
        assert len(response.headers["X-Request-ID"]) > 10

    def test_middleware_preserves_incoming_request_id(self, rf: RequestFactory):
        custom_id = "custom-trace-uuid-12345"

        def dummy_view(req):
            assert req.id == custom_id
            from django.http import HttpResponse

            return HttpResponse("OK")

        middleware = RequestIDMiddleware(dummy_view)
        request = rf.get("/api/v1/monitors/", HTTP_X_REQUEST_ID=custom_id)
        response = middleware(request)

        assert response.headers["X-Request-ID"] == custom_id


@pytest.mark.unit
class TestStructuredJSONFormatter:
    def test_json_formatter_produces_valid_json(self):
        formatter = StructuredJSONFormatter()
        record = logging.LogRecord(
            name="checks.tasks",
            level=logging.INFO,
            pathname=__file__,
            lineno=42,
            msg="Probed monitor 123",
            args=(),
            exc_info=None,
        )
        record.monitor_id = 123
        record.region = "eu-central"

        output = formatter.format(record)
        data = json.loads(output)

        assert data["level"] == "INFO"
        assert data["logger"] == "checks.tasks"
        assert data["message"] == "Probed monitor 123"
        assert data["monitor_id"] == 123
        assert data["region"] == "eu-central"
        assert "timestamp" in data
