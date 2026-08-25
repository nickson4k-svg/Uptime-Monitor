"""Local development settings."""

from .base import *  # noqa: F401, F403
from .base import BASE_DIR

DEBUG = True

CORS_ALLOW_ALL_ORIGINS = True

# ─── Debug toolbar ────────────────────────────────────────────────────────────
try:
    import debug_toolbar  # noqa: F401

    INSTALLED_APPS = INSTALLED_APPS + ["debug_toolbar"]  # type: ignore[name-defined]  # noqa: F405
    MIDDLEWARE = ["debug_toolbar.middleware.DebugToolbarMiddleware"] + MIDDLEWARE  # type: ignore[name-defined]  # noqa: F405
    INTERNAL_IPS = ["127.0.0.1"]
except ImportError:
    pass

# ─── Email override for dev ───────────────────────────────────────────────────
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# ─── Static files for dev ─────────────────────────────────────────────────────
STATICFILES_DIRS = [BASE_DIR / "static"] if (BASE_DIR / "static").exists() else []

# ─── Database & Channels fallback for local dev ──────────────────────────────
USE_SQLITE = config("USE_SQLITE", default=True, cast=bool)

if USE_SQLITE:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        }
    }

# ─── Disable strict password validation for dev ──────────────────────────────
AUTH_PASSWORD_VALIDATORS = []


