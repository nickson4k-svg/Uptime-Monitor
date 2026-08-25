"""Test settings — fast, in-memory DB, no external services."""

from .base import *  # noqa: F401, F403

# ─── Use SQLite for tests (faster) ────────────────────────────────────────────
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# ─── Sync channel layer for tests ─────────────────────────────────────────────
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}

# ─── Celery always eager in tests ─────────────────────────────────────────────
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# ─── Password hasher — fastest for tests ──────────────────────────────────────
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# ─── Email backend ────────────────────────────────────────────────────────────
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# ─── Disable field encryption in tests ────────────────────────────────────────
FIELD_ENCRYPTION_KEY = "test-key-not-used-for-encryption-in-tests-123456"

# ─── Disable throttling in tests ──────────────────────────────────────────────
REST_FRAMEWORK = {
    **REST_FRAMEWORK,  # type: ignore[name-defined]  # noqa: F405
    "DEFAULT_THROTTLE_CLASSES": [],
    "DEFAULT_THROTTLE_RATES": {},
}

SECRET_KEY = "test-secret-key-not-for-production"  # noqa: S105
DEBUG = True
