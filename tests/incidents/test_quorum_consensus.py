"""
Unit tests for Multi-Region Quorum Consensus in IncidentService.
"""

import pytest

from checks.checkers.base import CheckResultData
from checks.models import CheckErrorType, CheckResult, CheckStatus
from incidents.models import Incident
from incidents.services import IncidentService
from monitors.models import Monitor, MonitorStatus


@pytest.fixture
def multi_region_monitor(db, user):
    return Monitor.objects.create(
        owner=user,
        name="Multi-Region Global Service",
        url="https://api.example.com/health",
        regions=["eu-central", "us-east", "ap-southeast"],
        quorum_threshold=2,
        failure_threshold=1,
        is_active=True,
    )


@pytest.mark.django_db
class TestMultiRegionQuorumConsensus:
    def test_single_region_failure_below_quorum_does_not_open_incident(
        self, multi_region_monitor
    ):
        # Only eu-central fails (1/3 failing, quorum requires 2)
        result_eu = CheckResultData(
            status=CheckStatus.DOWN,
            response_time_ms=None,
            http_code=500,
            error_type=CheckErrorType.HTTP_ERROR,
            error_message="Server Error",
        )
        CheckResult.objects.create(
            monitor=multi_region_monitor,
            region="eu-central",
            status=CheckStatus.DOWN,
            error_type=CheckErrorType.HTTP_ERROR,
        )

        IncidentService.handle_check_result(
            multi_region_monitor.id, result_eu, region="eu-central"
        )

        multi_region_monitor.refresh_from_db()
        assert not Incident.objects.filter(monitor=multi_region_monitor).exists()
        assert multi_region_monitor.consecutive_failures == 0

    def test_quorum_reached_opens_incident_with_consensus_message(
        self, multi_region_monitor
    ):
        # 1. eu-central failed earlier
        CheckResult.objects.create(
            monitor=multi_region_monitor,
            region="eu-central",
            status=CheckStatus.DOWN,
            error_type=CheckErrorType.HTTP_ERROR,
            error_message="HTTP 500",
        )

        # 2. us-east now also fails (2/3 failing >= quorum_threshold 2)
        result_us = CheckResultData(
            status=CheckStatus.DOWN,
            response_time_ms=None,
            http_code=500,
            error_type=CheckErrorType.HTTP_ERROR,
            error_message="HTTP 500",
        )
        CheckResult.objects.create(
            monitor=multi_region_monitor,
            region="us-east",
            status=CheckStatus.DOWN,
            error_type=CheckErrorType.HTTP_ERROR,
            error_message="HTTP 500",
        )

        IncidentService.handle_check_result(
            multi_region_monitor.id, result_us, region="us-east"
        )

        multi_region_monitor.refresh_from_db()
        assert multi_region_monitor.current_status == MonitorStatus.DOWN
        assert multi_region_monitor.consecutive_failures >= 1

        incident = Incident.objects.filter(
            monitor=multi_region_monitor, is_resolved=False
        ).first()
        assert incident is not None
        assert "2/3 regions" in incident.root_cause_message
        assert "eu-central" in incident.root_cause_message
        assert "us-east" in incident.root_cause_message

    def test_recovery_in_region_resolves_open_incident(self, multi_region_monitor):
        # Open incident
        Incident.objects.create(
            monitor=multi_region_monitor,
            failure_count=2,
            root_cause_error=CheckErrorType.HTTP_ERROR,
            root_cause_message="Consensus outage confirmed",
        )
        multi_region_monitor.current_status = MonitorStatus.DOWN
        multi_region_monitor.consecutive_failures = 2
        multi_region_monitor.save()

        # Healthy check comes in
        result_up = CheckResultData(
            status=CheckStatus.UP,
            response_time_ms=120,
            http_code=200,
            error_type=CheckErrorType.NONE,
            error_message="",
        )
        CheckResult.objects.create(
            monitor=multi_region_monitor,
            region="eu-central",
            status=CheckStatus.UP,
        )

        IncidentService.handle_check_result(
            multi_region_monitor.id, result_up, region="eu-central"
        )

        multi_region_monitor.refresh_from_db()
        assert multi_region_monitor.current_status == MonitorStatus.UP
        assert multi_region_monitor.consecutive_failures == 0

        incident = Incident.objects.filter(monitor=multi_region_monitor).first()
        assert incident.is_resolved is True
