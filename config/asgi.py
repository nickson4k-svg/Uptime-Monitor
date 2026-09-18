"""
ASGI config — Django Channels wraps the Django WSGI app.
Routing: HTTP → Django, WebSocket → Channels consumers.
JWT auth middleware applied at WebSocket layer only.
"""

import os

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

# Initialize Django before importing apps
django_asgi_app = get_asgi_application()

from dashboard.middleware import WebsocketJWTAuthMiddleware  # noqa: E402
from dashboard.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AllowedHostsOriginValidator(
            # JWT auth middleware validates token from query param
            WebsocketJWTAuthMiddleware(URLRouter(websocket_urlpatterns))
        ),
    }
)
