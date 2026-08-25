"""
Incident service — manages incident lifecycle and notification dispatch.

Key design decisions:

1. select_for_update() on Monitor:
   - Prevents race condition where two Celery workers process the same monitor
     simultaneously and open duplicate incidents.
   - Uses NOWAIT=False (blocking) — acceptable since check tasks should not
     overlap (dispatched at > task execution time).

2. No retry on notification:
   - Notification task failure does NOT re-open incident.
   - Notification task has its own retry logic.

3. Atomic transactions:
   - Monitor status update + Incident creation/resolution in single DB transaction.
   - If notification fails, incident state is still correct.
"""

import logging
from contextlib import contextmanager

from django.db import transaction

from checks.models import CheckStatus
from checks.services import CheckResultData
from incidents.models import Incident
from monitors.models import Monitor, MonitorStatus

logger = logging.getLogger(__name__)


class IncidentService:
    """
    Handles the down/up state machine for a monitor after each check.
    Supports Multi-Region Quorum Consensus to prevent localized network false-alarms.
    """

    @staticmethod
    @transaction.atomic
    def handle_check_result(monitor_id: int, result: "CheckResultData", region: str = "eu-central") -> None:
        """
        Process a check result and update Monitor + Incident state.
        Called from check_monitor Celery task after persisting CheckResult.
        """
        try:
            monitor = Monitor.objects.select_for_update(nowait=True).get(pk=monitor_id)
        except Monitor.DoesNotExist:
            logger.warning("Monitor %s not found — skipping incident handling", monitor_id)
            return

        if result.status == CheckStatus.UP:
            IncidentService._handle_up(monitor, region)
        else:
            IncidentService._handle_down(monitor, result, region)

    @staticmethod
    def _handle_up(monitor: Monitor, region: str) -> None:
        """Handle a successful check — reset failure counter, resolve open incidents."""
        was_down = monitor.consecutive_failures > 0

        monitor.consecutive_failures = 0
        monitor.current_status = MonitorStatus.UP
        monitor.save(update_fields=["consecutive_failures", "current_status", "updated_at"])

        if was_down:
            # Resolve any open incidents
            open_incidents = Incident.objects.filter(
                monitor=monitor, is_resolved=False
            ).select_for_update(nowait=True)

            for incident in open_incidents:
                incident.resolve()
                incident.save(update_fields=["is_resolved", "resolved_at"])

                if not incident.resolved_alert_sent:
                    # Import here to avoid circular import
                    from notifications.tasks import dispatch_incident_notification
                    dispatch_incident_notification.delay(incident.pk, event="resolved")
                    logger.info("Dispatched resolved notification for incident %s (confirmed by %s)", incident.pk, region)

    @staticmethod
    def _handle_down(monitor: Monitor, result: "CheckResultData", region: str) -> None:
        """
        Handle a failed check — evaluate multi-region quorum before declaring incident.
        """
        configured_regions = monitor.get_regions()
        quorum_needed = monitor.quorum_threshold or 1

        # Evaluate failing regions from recent checks
        failing_regions = {region}
        for r in configured_regions:
            if r == region:
                continue
            last_r_check = monitor.check_results.filter(region=r).order_by("-checked_at").first()
            if last_r_check and last_r_check.status == CheckStatus.DOWN:
                failing_regions.add(r)

        has_quorum = len(failing_regions) >= quorum_needed

        if not has_quorum:
            logger.info(
                "Monitor %s localized degradation in %s (%d/%d regions failing, quorum requires %d) — incident suppressed.",
                monitor.pk,
                region,
                len(failing_regions),
                len(configured_regions),
                quorum_needed,
            )
            return

        monitor.consecutive_failures += 1
        monitor.current_status = MonitorStatus.DOWN
        monitor.save(update_fields=["consecutive_failures", "current_status", "updated_at"])

        logger.info(
            "Monitor %s DOWN with quorum [%s] (consecutive_failures=%s, threshold=%s)",
            monitor.pk,
            ", ".join(failing_regions),
            monitor.consecutive_failures,
            monitor.failure_threshold,
        )

        # Check if we should open an incident
        threshold_reached = monitor.consecutive_failures >= monitor.failure_threshold
        has_open_incident = Incident.objects.filter(
            monitor=monitor, is_resolved=False
        ).exists()

        if threshold_reached and not has_open_incident:
            regions_str = ", ".join(sorted(failing_regions))
            if len(configured_regions) > 1:
                root_cause = f"Outage confirmed by {len(failing_regions)}/{len(configured_regions)} regions ({regions_str}): {result.error_message or result.error_type}"
            else:
                root_cause = result.error_message

            incident = Incident.objects.create(
                monitor=monitor,
                failure_count=monitor.consecutive_failures,
                root_cause_error=result.error_type,
                root_cause_message=root_cause,
            )
            logger.warning("Opened incident %s for monitor %s (Quorum: %s)", incident.pk, monitor.pk, regions_str)

            # Dispatch notification asynchronously
            from notifications.tasks import dispatch_incident_notification
            dispatch_incident_notification.delay(incident.pk, event="opened")

        elif has_open_incident:
            # Update failure count on existing incident
            Incident.objects.filter(
                monitor=monitor, is_resolved=False
            ).update(failure_count=monitor.consecutive_failures)

