"""Email notification backend."""

import logging

from django.conf import settings
from django.core.mail import send_mail

from . import NotificationPayload, build_message

logger = logging.getLogger(__name__)


def notify(config: dict, payload: NotificationPayload) -> None:
    """
    Send email notification.

    config shape: {"email": "user@example.com"}
    """
    recipient = config.get("email")
    if not recipient:
        raise ValueError("Email config missing 'email' key")

    subject, body = build_message(payload)

    send_mail(
        subject=subject,
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[recipient],
        fail_silently=False,
    )
    logger.info(
        "Email notification sent to %s for incident %s", recipient, payload.incident_id
    )
