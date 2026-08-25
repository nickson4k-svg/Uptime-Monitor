"""
WebSocket consumer tests using Django Channels test helpers.
"""

import json

import pytest
from channels.testing import WebsocketCommunicator
from django.test import override_settings

from config.asgi import application


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestDashboardConsumer:
    async def _connect_authenticated(self, user):
        """Helper: create JWT token and connect WebSocket."""
        from asgiref.sync import sync_to_async
        from rest_framework_simplejwt.tokens import RefreshToken

        token = await sync_to_async(lambda: str(RefreshToken.for_user(user).access_token))()
        communicator = WebsocketCommunicator(
            application,
            f"/ws/dashboard/?token={token}",
            headers=[(b"origin", b"http://localhost")],
        )
        connected, code = await communicator.connect()
        return communicator, connected, code

    async def test_authenticated_user_can_connect(self, user):
        communicator, connected, _ = await self._connect_authenticated(user)
        assert connected is True

        # Should receive connection_established message
        response = await communicator.receive_json_from()
        assert response["type"] == "connection_established"
        assert response["user_id"] == str(user.id)

        await communicator.disconnect()

    async def test_unauthenticated_connection_rejected(self):
        communicator = WebsocketCommunicator(application, "/ws/dashboard/")
        connected, code = await communicator.connect()
        # Should be rejected with code 4001
        assert not connected or code == 4001
        await communicator.disconnect()

    async def test_invalid_token_rejected(self):
        communicator = WebsocketCommunicator(
            application,
            "/ws/dashboard/?token=invalid.token.here",
        )
        connected, code = await communicator.connect()
        assert not connected or code == 4001
        await communicator.disconnect()

    async def test_ping_pong(self, user):
        communicator, connected, _ = await self._connect_authenticated(user)
        assert connected

        # Consume the connection_established message
        await communicator.receive_json_from()

        # Send ping
        await communicator.send_json_to({"type": "ping"})
        response = await communicator.receive_json_from()
        assert response["type"] == "pong"

        await communicator.disconnect()

    async def test_receives_status_update_from_channel_layer(self, user):
        """
        Simulate a Celery worker sending a status update via channel layer.
        Consumer should relay it to the WebSocket client.
        """
        from asgiref.sync import sync_to_async
        from channels.layers import get_channel_layer

        communicator, connected, _ = await self._connect_authenticated(user)
        assert connected

        # Consume connection_established
        await communicator.receive_json_from()

        # Simulate Celery worker pushing an event
        channel_layer = get_channel_layer()
        group_name = f"monitor_updates_{user.id}"

        await channel_layer.group_send(
            group_name,
            {
                "type": "monitor.status_update",
                "monitor_id": 999,
                "status": "down",
                "response_time_ms": None,
                "http_code": None,
                "checked_at": "2024-01-15T10:00:00+00:00",
            },
        )

        # Consumer should relay to browser
        response = await communicator.receive_json_from(timeout=5)
        assert response["type"] == "monitor_status_update"
        assert response["monitor_id"] == 999
        assert response["status"] == "down"

        await communicator.disconnect()
