"""
Notification Celery tasks.

dispatch_incident_notification is called from IncidentService.
It loads all active AlertChannels for the monitor's owner,
dispatches individual send_notification tasks per channel.

Retry strategy:
- 3 retries with exponential backoff (30s → 60s → 120s).
- After all retries fail: log error, mark channel as "last_error" (future feature).
- Failure on one channel does NOT affect others (separate tasks).
"""

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(
    name="notifications.tasks.dispatch_incident_notification",
    queue="notifications",
    ignore_result=True,
)
def dispatch_incident_notification(incident_id: int, event: str) -> None:
    """
    Load incident + monitor → find all active alert channels → dispatch individual sends.
    event: "opened" | "resolved"
    """
    from incidents.models import Incident
    from notifications.models import MonitorAlert

    try:
        incident = Incident.objects.select_related("monitor__owner").get(pk=incident_id)
    except Incident.DoesNotExist:
        logger.error("Incident %s not found — cannot dispatch notification", incident_id)
        return

    # Find all active channels connected to this monitor
    alert_channels = MonitorAlert.objects.filter(
        monitor=incident.monitor,
        channel__is_active=True,
    ).select_related("channel")

    if not alert_channels.exists():
        logger.info("No active alert channels for monitor %s", incident.monitor_id)
        return

    for monitor_alert in alert_channels:
        send_notification.delay(
            alert_channel_id=monitor_alert.channel_id,
            incident_id=incident_id,
            event=event,
        )

    # Mark that alerts were dispatched (prevent duplicate dispatch)
    if event == "opened":
        Incident.objects.filter(pk=incident_id).update(alert_sent=True)
    elif event == "resolved":
        Incident.objects.filter(pk=incident_id).update(resolved_alert_sent=True)


@shared_task(
    name="notifications.tasks.send_notification",
    bind=True,
    queue="notifications",
    max_retries=3,
    default_retry_delay=30,
)
def send_notification(self, alert_channel_id: int, incident_id: int, event: str) -> None:
    """
    Send one notification to one channel for one incident.
    Retries 3 times with exponential backoff on failure.
    """
    from incidents.models import Incident
    from notifications.backends import NotificationPayload
    from notifications.models import AlertChannel, ChannelType

    try:
        channel = AlertChannel.objects.get(pk=alert_channel_id, is_active=True)
        incident = Incident.objects.select_related("monitor").get(pk=incident_id)
    except (AlertChannel.DoesNotExist, Incident.DoesNotExist) as exc:
        logger.warning("Cannot send notification: %s", exc)
        return

    monitor = incident.monitor
    payload = NotificationPayload(
        event=event,
        monitor_name=monitor.name,
        monitor_url=monitor.url,
        monitor_id=monitor.pk,
        incident_id=incident.pk,
        started_at=incident.started_at.isoformat(),
        resolved_at=incident.resolved_at.isoformat() if incident.resolved_at else None,
        failure_count=incident.failure_count,
        root_cause=incident.root_cause_message,
        duration_seconds=incident.duration_seconds,
    )

    # Dispatch to the correct backend
    try:
        if channel.channel_type == ChannelType.EMAIL:
            from notifications.backends.email import notify
        elif channel.channel_type == ChannelType.TELEGRAM:
            from notifications.backends.telegram import notify
        elif channel.channel_type == ChannelType.SLACK:
            from notifications.backends.slack import notify
        else:
            logger.error("Unknown channel type: %s", channel.channel_type)
            return

        notify(channel.config, payload)
        logger.info(
            "Notification sent: channel=%s incident=%s event=%s",
            channel.pk,
            incident_id,
            event,
        )

    except Exception as exc:
        # Exponential backoff: 30s, 60s, 120s
        retry_delay = 30 * (2 ** self.request.retries)
        logger.warning(
            "Notification failed (attempt %d/3): %s — retrying in %ds",
            self.request.retries + 1,
            exc,
            retry_delay,
        )
        raise self.retry(exc=exc, countdown=retry_delay)
