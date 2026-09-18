"""Production settings."""

import os

from decouple import config

from .base import *  # noqa: F401, F403
from .base import MIDDLEWARE

DEBUG = config("DEBUG", default=False, cast=bool)

ALLOWED_HOSTS = config(
    "ALLOWED_HOSTS",
    default="*",
    cast=lambda v: [s.strip() for s in v.split(",") if s],
)
if os.environ.get("VERCEL") or not ALLOWED_HOSTS:
    ALLOWED_HOSTS = ["*"]

# ─── Security headers & Proxy SSL ─────────────────────────────────────────────
# In Vercel / serverless reverse proxy, edge handles HTTPS termination
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=False, cast=bool)

SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

CSRF_TRUSTED_ORIGINS = config(
    "CSRF_TRUSTED_ORIGINS",
    default="https://*.vercel.app,http://localhost,http://127.0.0.1",
    cast=lambda v: [s.strip() for s in v.split(",") if s],
)

# ─── Static files (WhiteNoise) ────────────────────────────────────────────────
try:
    import whitenoise  # noqa: F401

    if "whitenoise.middleware.WhiteNoiseMiddleware" not in MIDDLEWARE:
        try:
            sec_idx = MIDDLEWARE.index("django.middleware.security.SecurityMiddleware")
            MIDDLEWARE.insert(sec_idx + 1, "whitenoise.middleware.WhiteNoiseMiddleware")
        except ValueError:
            MIDDLEWARE = ["whitenoise.middleware.WhiteNoiseMiddleware"] + MIDDLEWARE

    STATICFILES_STORAGE = "whitenoise.storage.CompressedStaticFilesStorage"
except ImportError:
    pass

# ─── Channel Layers Fallback ──────────────────────────────────────────────────
# In serverless environments without an external Redis instance, fallback to memory
if not config("CHANNEL_LAYERS_REDIS_URL", default="") and not config(
    "REDIS_URL", default=""
):
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        }
    }

# ─── CORS ─────────────────────────────────────────────────────────────────────
CORS_ALLOWED_ORIGINS = config(
    "CORS_ALLOWED_ORIGINS",
    default="",
    cast=lambda v: [s.strip() for s in v.split(",") if s],
)
if not CORS_ALLOWED_ORIGINS:
    CORS_ALLOW_ALL_ORIGINS = True

# ─── Sentry ───────────────────────────────────────────────────────────────────
SENTRY_DSN = config("SENTRY_DSN", default="")
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.redis import RedisIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration(), CeleryIntegration(), RedisIntegration()],
        traces_sample_rate=0.1,
        send_default_pii=False,
    )
