"""
WebSocket JWT Authentication Middleware.

Standard Django auth middleware doesn't apply to WebSocket connections.
This middleware validates a JWT access token from the query string:
  wss://host/ws/dashboard/?token=<access_token>

Why query param (not header)?
  - Browser WebSocket API doesn't support custom headers.
  - Query param is the standard approach for WS auth.
  - Token is short-lived (15 min) — minimal exposure risk.
  - Over wss:// (TLS) the query string is encrypted.

Implementation:
  - Wraps the inner ASGI app.
  - Validates token synchronously (JWT decode is CPU-bound, not I/O).
  - Sets scope["user"] for the downstream consumer.
"""

import logging
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import AccessToken

logger = logging.getLogger(__name__)


@database_sync_to_async
def get_user_from_token(token_str: str):
    """Validate JWT and return User or AnonymousUser."""
    from django.contrib.auth import get_user_model

    User = get_user_model()

    try:
        token = AccessToken(token_str)
        user_id = token["user_id"]
        return User.objects.get(pk=user_id, is_active=True)
    except (InvalidToken, TokenError, User.DoesNotExist, KeyError) as exc:
        logger.debug("WebSocket JWT validation failed: %s", exc)
        return AnonymousUser()


class WebsocketJWTAuthMiddleware(BaseMiddleware):
    """
    ASGI middleware that validates JWT token from query string
    and sets scope["user"] before passing to the consumer.
    """

    async def __call__(self, scope, receive, send):
        if scope["type"] == "websocket":
            query_string = scope.get("query_string", b"").decode()
            params = parse_qs(query_string)
            token_list = params.get("token", [])

            if token_list:
                scope["user"] = await get_user_from_token(token_list[0])
            else:
                scope["user"] = AnonymousUser()

        return await super().__call__(scope, receive, send)
