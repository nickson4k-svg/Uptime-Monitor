"""
Dashboard WebSocket consumer.

Flow:
  1. Browser opens wss://host/ws/dashboard/?token=<jwt_access_token>
  2. WebsocketJWTAuthMiddleware validates token, sets scope["user"]
  3. DashboardConsumer.connect():
     - If user is authenticated → join group "monitor_updates_{user_id}"
     - Else → close(4001)
  4. check_monitor Celery task:
     - After each check, calls channel_layer.group_send(group_name, event)
  5. Consumer receives event → sends JSON to browser WebSocket
  6. Browser JS updates the UI in real-time

Why group per user (not per monitor)?
  - A user has multiple monitors.
  - One WebSocket connection covers all their monitors.
  - Celery sends to the user group — consumer relays to browser.
  - If user has two browser tabs open, both receive updates.
"""

import json
import logging

from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger(__name__)


class DashboardConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for the private dashboard.
    Receives live monitor status updates from Celery via Redis channel layer.
    """

    async def connect(self):
        user = self.scope.get("user")

        if not user or not user.is_authenticated:
            logger.warning("WebSocket connection rejected — unauthenticated")
            await self.close(code=4001)
            return

        # Group name: one group per user — all their monitors share it
        self.group_name = f"monitor_updates_{user.id}"
        self.user_id = str(user.id)

        # Subscribe to the user's update group
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        logger.info("WebSocket connected: user=%s group=%s", user.id, self.group_name)

        # Send initial "connected" confirmation
        await self.send(
            text_data=json.dumps(
                {"type": "connection_established", "user_id": self.user_id}
            )
        )

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
            logger.info(
                "WebSocket disconnected: user=%s code=%s", self.user_id, close_code
            )

    async def receive(self, text_data=None, bytes_data=None):
        """
        Receive messages from browser (optional — e.g., ping/pong keepalive).
        The dashboard is mostly server→client, but we handle ping here.
        """
        if text_data:
            try:
                data = json.loads(text_data)
                if data.get("type") == "ping":
                    await self.send(text_data=json.dumps({"type": "pong"}))
            except json.JSONDecodeError:
                pass

    # ── Event handlers (called by channel_layer.group_send) ───────────────────

    async def monitor_status_update(self, event):
        """
        Handles "monitor.status_update" events sent by check_monitor Celery task.

        The event type "monitor.status_update" maps to method "monitor_status_update"
        (dots replaced with underscores by Channels).

        Event shape (from tasks.py):
        {
            "type": "monitor.status_update",
            "monitor_id": 42,
            "status": "down",
            "response_time_ms": null,
            "http_code": null,
            "checked_at": "2024-01-15T10:30:00+00:00"
        }
        """
        await self.send(
            text_data=json.dumps(
                {
                    "type": "monitor_status_update",
                    "monitor_id": event["monitor_id"],
                    "status": event["status"],
                    "response_time_ms": event.get("response_time_ms"),
                    "http_code": event.get("http_code"),
                    "region": event.get("region", "eu-central"),
                    "checked_at": event["checked_at"],
                }
            )
        )
