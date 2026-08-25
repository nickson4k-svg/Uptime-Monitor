"""Telegram notification backend — uses Bot API sendMessage."""

import logging

import httpx

from . import NotificationPayload, build_message

logger = logging.getLogger(__name__)

TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"


def notify(config: dict, payload: NotificationPayload) -> None:
    """
    Send Telegram message via Bot API.

    config shape: {"bot_token": "...", "chat_id": "123456789"}
    """
    bot_token = config.get("bot_token")
    chat_id = config.get("chat_id")
    if not bot_token or not chat_id:
        raise ValueError("Telegram config missing 'bot_token' or 'chat_id'")

    subject, body = build_message(payload)
    text = f"*{subject}*\n\n{body}"

    url = TELEGRAM_API_URL.format(token=bot_token)
    response = httpx.post(
        url,
        json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
        },
        timeout=10,
    )
    response.raise_for_status()

    result = response.json()
    if not result.get("ok"):
        raise RuntimeError(f"Telegram API error: {result}")

    logger.info(
        "Telegram notification sent to chat_id=%s for incident %s",
        chat_id,
        payload.incident_id,
    )
