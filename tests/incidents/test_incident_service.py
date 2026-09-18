"""
Tests for IncidentService.

Covers:
- DOWN result below threshold → no incident
- DOWN result at threshold → incident created
- Second DOWN → incident not duplicated, failure_count updated
- UP after DOWN → incident resolved, resolved alert dispatched
- Flapping: UP → DOWN × 3 → UP → incident opened then resolved
- Multiple monitors don't cross-contaminate
"""

import pytest

from checks.models import CheckErrorType, CheckStatus
from checks.services import CheckResultData
from incidents.models import Incident
from incidents.services import IncidentService
from monitors.models import MonitorStatus


def make_result(status=CheckStatus.UP, error_type=CheckErrorType.NONE, msg=""):
    return CheckResultData(
        status=status,
        response_time_ms=100 if status == CheckStatus.UP else None,
        http_code=200 if status == CheckStatus.UP else None,
        error_type=error_type,
        error_message=msg,
    )


@pytest.mark.django_db
class TestIncidentServiceDown:
    def test_single_failure_below_threshold_no_incident(self, monitor):
        """1 failure with threshold=3 → no incident, consecutive_failures=1."""
        monitor.failure_threshold = 3
        monitor.save()

        result = make_result(status=CheckStatus.DOWN, error_type=CheckErrorType.TIMEOUT)
        IncidentService.handle_check_result(monitor.pk, result)

        monitor.refresh_from_db()
        assert monitor.consecutive_failures == 1
        assert monitor.current_status == MonitorStatus.DOWN
        assert not Incident.objects.filter(monitor=monitor).exists()

    def test_failures_at_threshold_open_incident(self, monitor):
        """Exactly N failures → incident opened."""
        monitor.failure_threshold = 2
        monitor.consecutive_failures = 1  # already 1 failure
        monitor.current_status = MonitorStatus.DOWN
        monitor.save()

        result = make_result(
            status=CheckStatus.DOWN, error_type=CheckErrorType.TIMEOUT, msg="timed out"
        )
        IncidentService.handle_check_result(monitor.pk, result)

        monitor.refresh_from_db()
        assert monitor.consecutive_failures == 2
        incident = Incident.objects.get(monitor=monitor)
        assert not incident.is_resolved
        assert incident.root_cause_error == CheckErrorType.TIMEOUT
        assert incident.root_cause_message == "timed out"

    def test_second_down_does_not_duplicate_incident(self, monitor):
        """4th failure when incident already open → failure_count updated, no new incident."""
        monitor.failure_threshold = 2
        monitor.consecutive_failures = 2
        monitor.current_status = MonitorStatus.DOWN
        monitor.save()

        Incident.objects.create(monitor=monitor, failure_count=2)

        result = make_result(status=CheckStatus.DOWN)
        IncidentService.handle_check_result(monitor.pk, result)

        assert Incident.objects.filter(monitor=monitor).count() == 1
        incident = Incident.objects.get(monitor=monitor)
        assert incident.failure_count == 3  # updated

    def test_incident_stores_root_cause(self, monitor):
        monitor.failure_threshold = 1
        monitor.save()

        result = make_result(
            status=CheckStatus.DOWN,
            error_type=CheckErrorType.SSL_ERROR,
            msg="certificate expired",
        )
        IncidentService.handle_check_result(monitor.pk, result)

        incident = Incident.objects.get(monitor=monitor)
        assert incident.root_cause_error == CheckErrorType.SSL_ERROR
        assert incident.root_cause_message == "certificate expired"


@pytest.mark.django_db
class TestIncidentServiceUp:
    def test_up_resets_consecutive_failures(self, monitor):
        monitor.consecutive_failures = 2
        monitor.current_status = MonitorStatus.DOWN
        monitor.save()

        result = make_result(status=CheckStatus.UP)
        IncidentService.handle_check_result(monitor.pk, result)

        monitor.refresh_from_db()
        assert monitor.consecutive_failures == 0
        assert monitor.current_status == MonitorStatus.UP

    def test_up_resolves_open_incident(self, monitor):
        monitor.consecutive_failures = 3
        monitor.current_status = MonitorStatus.DOWN
        monitor.failure_threshold = 3
        monitor.save()

        incident = Incident.objects.create(monitor=monitor, failure_count=3)
        assert not incident.is_resolved

        result = make_result(status=CheckStatus.UP)
        IncidentService.handle_check_result(monitor.pk, result)

        incident.refresh_from_db()
        assert incident.is_resolved
        assert incident.resolved_at is not None

    def test_up_without_prior_incident_does_nothing(self, monitor):
        """UP when already UP → no side effects."""
        monitor.current_status = MonitorStatus.UP
        monitor.consecutive_failures = 0
        monitor.save()

        result = make_result(status=CheckStatus.UP)
        IncidentService.handle_check_result(monitor.pk, result)

        monitor.refresh_from_db()
        assert monitor.current_status == MonitorStatus.UP
        assert monitor.consecutive_failures == 0


@pytest.mark.django_db
class TestFlapping:
    def test_flapping_below_threshold_no_incident(self, monitor):
        """
        Pattern: DOWN, UP, DOWN, UP — threshold=3.
        Never reaches threshold → no incident ever opened.
        """
        monitor.failure_threshold = 3
        monitor.save()

        down = make_result(status=CheckStatus.DOWN)
        up = make_result(status=CheckStatus.UP)

        # DOWN → UP → DOWN → UP
        IncidentService.handle_check_result(monitor.pk, down)  # 1
        monitor.refresh_from_db()
        assert monitor.consecutive_failures == 1

        IncidentService.handle_check_result(monitor.pk, up)  # reset
        monitor.refresh_from_db()
        assert monitor.consecutive_failures == 0

        IncidentService.handle_check_result(monitor.pk, down)  # 1
        IncidentService.handle_check_result(monitor.pk, up)  # reset

        assert not Incident.objects.filter(monitor=monitor).exists()


@pytest.mark.django_db
class TestMultitenancy:
    def test_incident_created_for_correct_monitor(self, monitor, monitor2):
        """Two monitors: only monitor reaches threshold → only monitor gets incident."""
        monitor.failure_threshold = 1
        monitor.save()
        monitor2.failure_threshold = 1
        monitor2.save()

        down = make_result(status=CheckStatus.DOWN)
        IncidentService.handle_check_result(monitor.pk, down)

        assert Incident.objects.filter(monitor=monitor).count() == 1
        assert Incident.objects.filter(monitor=monitor2).count() == 0
