"""Slack notification backend — uses Incoming Webhooks."""

import logging

import httpx

from . import NotificationPayload, build_message

logger = logging.getLogger(__name__)


def notify(config: dict, payload: NotificationPayload) -> None:
    """
    Send Slack message via Incoming Webhook.

    config shape: {"webhook_url": "https://hooks.slack.com/services/T.../B.../..."}

    Uses Block Kit for rich formatting.
    """
    webhook_url = config.get("webhook_url")
    if not webhook_url:
        raise ValueError("Slack config missing 'webhook_url'")

    subject, body = build_message(payload)

    color = "#d32f2f" if payload.event == "opened" else "#388e3c"
    emoji = "🔴" if payload.event == "opened" else "✅"

    slack_payload = {
        "attachments": [
            {
                "color": color,
                "blocks": [
                    {
                        "type": "header",
                        "text": {"type": "plain_text", "text": f"{emoji} {subject}"},
                    },
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": f"```{body}```"},
                    },
                ],
            }
        ]
    }

    response = httpx.post(webhook_url, json=slack_payload, timeout=10)
    response.raise_for_status()

    logger.info("Slack notification sent for incident %s", payload.incident_id)
