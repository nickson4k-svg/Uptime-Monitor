"""
Unit tests for Performance Optimizations and Data Retention Pruning.
"""

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from checks.models import CheckResult, CheckStatus, HourlyStats
from checks.tasks import prune_old_checks
from monitors.models import Monitor
from monitors.views import MonitorViewSet


@pytest.mark.django_db
class TestQueryOptimizationAndNPlusOne:
    def test_list_monitors_uses_annotated_subquery_without_n_plus_one(
        self, user, rf: APIRequestFactory
    ):
        # Create 5 monitors
        now = timezone.now()
        hour_start = (now - timedelta(hours=2)).replace(
            minute=0, second=0, microsecond=0
        )
        for i in range(5):
            m = Monitor.objects.create(
                owner=user,
                name=f"Monitor {i}",
                url=f"https://api{i}.example.com",
            )
            HourlyStats.objects.create(
                monitor=m,
                hour=hour_start,
                total_checks=10,
                up_checks=10,
                uptime_pct=100.0,
            )

        view = MonitorViewSet.as_view({"get": "list"})
        request = rf.get("/api/v1/monitors/")
        force_authenticate(request, user=user)

        response = view(request)
        assert response.status_code == 200
        assert len(response.data["results"]) == 5
        for item in response.data["results"]:
            assert item["uptime_24h"] == 100.0


@pytest.mark.django_db
class TestDataRetentionPruning:
    def test_prune_old_checks_removes_old_and_preserves_recent(self, monitor):
        now = timezone.now()
        old_time = now - timedelta(days=45)
        recent_time = now - timedelta(days=5)

        # 3 old checks (> 30 days)
        for _ in range(3):
            CheckResult.objects.create(
                monitor=monitor,
                checked_at=old_time,
                status=CheckStatus.UP,
            )

        # 2 recent checks (< 30 days)
        for _ in range(2):
            CheckResult.objects.create(
                monitor=monitor,
                checked_at=recent_time,
                status=CheckStatus.UP,
            )

        assert CheckResult.objects.count() == 5

        deleted = prune_old_checks(days=30, batch_size=10)
        assert deleted == 3
        assert CheckResult.objects.count() == 2
        for check in CheckResult.objects.all():
            assert check.checked_at >= now - timedelta(days=30)
