"""
Incident models.

Design decisions:

1. One active incident per monitor at a time:
   - Enforced by service layer (IncidentService.handle_check_result).
   - No DB constraint — to avoid race condition complexity with Celery.
   - Service uses select_for_update() on Monitor to prevent duplicate incidents.

2. Lifecycle: OPEN → RESOLVED (no other states for simplicity):
   - started_at: when first DOWN check crossed failure_threshold.
   - resolved_at: when first UP check came after the incident.
   - root_cause: copied from first CheckResult's error_message — immutable snapshot.

3. notification_sent flag:
   - Prevents duplicate alert spam.
   - Set to True after first successful notification dispatch.
   - Separate flag for "resolved" notification.
"""

from django.db import models
from django.utils import timezone

from monitors.models import Monitor


class Incident(models.Model):
    """
    An incident represents a period of downtime for a monitor.
    """

    monitor = models.ForeignKey(
        Monitor,
        on_delete=models.CASCADE,
        related_name="incidents",
    )

    started_at = models.DateTimeField(default=timezone.now, db_index=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    is_resolved = models.BooleanField(default=False, db_index=True)

    # Failure tracking
    failure_count = models.PositiveIntegerField(default=1)
    root_cause_error = models.CharField(
        max_length=50,
        blank=True,
        help_text="CheckErrorType from the first failing check.",
    )
    root_cause_message = models.TextField(
        blank=True,
        help_text="Error message from the first failing check — immutable snapshot.",
    )

    # Notification tracking
    alert_sent = models.BooleanField(default=False)
    resolved_alert_sent = models.BooleanField(default=False)

    class Meta:
        db_table = "incidents_incident"
        ordering = ["-started_at"]
        indexes = [
            models.Index(
                fields=["monitor", "is_resolved"], name="idx_incident_monitor_resolved"
            ),
            models.Index(fields=["started_at"], name="idx_incident_started"),
        ]

    def __str__(self) -> str:
        status = "RESOLVED" if self.is_resolved else "OPEN"
        return f"Incident[{status}] monitor={self.monitor_id} started={self.started_at}"

    @property
    def duration_seconds(self) -> int | None:
        """Duration of the incident in seconds. None if still open."""
        if self.resolved_at is None:
            return None
        return int((self.resolved_at - self.started_at).total_seconds())

    def resolve(self) -> None:
        """Mark this incident as resolved. Call save() after."""
        self.is_resolved = True
        self.resolved_at = timezone.now()
