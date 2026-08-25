"""
Notification backends — one module per channel type.
Each backend implements the same interface: notify(config: dict, payload: NotificationPayload).
"""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class NotificationPayload:
    """Structured data passed to all notification backends."""
    event: str           # "opened" | "resolved"
    monitor_name: str
    monitor_url: str
    monitor_id: int
    incident_id: int
    started_at: str
    resolved_at: str | None
    failure_count: int
    root_cause: str
    duration_seconds: int | None


def build_message(payload: NotificationPayload) -> tuple[str, str]:
    """Build subject + body text for all backends."""
    if payload.event == "opened":
        subject = f"🔴 DOWN: {payload.monitor_name}"
        body = (
            f"Monitor: {payload.monitor_name}\n"
            f"URL: {payload.monitor_url}\n"
            f"Status: DOWN ❌\n"
            f"Since: {payload.started_at}\n"
            f"Failures: {payload.failure_count}\n"
            f"Cause: {payload.root_cause}\n"
        )
    else:
        subject = f"✅ RESOLVED: {payload.monitor_name}"
        body = (
            f"Monitor: {payload.monitor_name}\n"
            f"URL: {payload.monitor_url}\n"
            f"Status: UP ✅\n"
            f"Resolved at: {payload.resolved_at}\n"
            f"Duration: {payload.duration_seconds}s\n"
        )
    return subject, body
