"""Production settings."""

from decouple import config

from .base import *  # noqa: F401, F403

DEBUG = False

ALLOWED_HOSTS = config(
    "ALLOWED_HOSTS",
    default=".vercel.app,localhost,127.0.0.1",
    cast=lambda v: [s.strip() for s in v.split(",") if s],
)

# ─── Security headers ─────────────────────────────────────────────────────────
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# ─── Static files (WhiteNoise) ────────────────────────────────────────────────
try:
    import whitenoise  # noqa: F401

    MIDDLEWARE = ["whitenoise.middleware.WhiteNoiseMiddleware"] + MIDDLEWARE  # type: ignore[name-defined]  # noqa: F405
    STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
except ImportError:
    pass

# ─── CORS ─────────────────────────────────────────────────────────────────────
CORS_ALLOWED_ORIGINS = config(
    "CORS_ALLOWED_ORIGINS",
    default="",
    cast=lambda v: [s.strip() for s in v.split(",") if s],
)

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
