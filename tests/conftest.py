"""
Shared pytest fixtures and factories.

Uses factory_boy for model factories — avoids fixture coupling.
"""

import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.fixture
def user(db):
    """A regular test user."""
    return User.objects.create_user(
        email="test@example.com",
        password="testpassword123",
        full_name="Test User",
    )


@pytest.fixture
def user2(db):
    """A second user — for multitenancy tests."""
    return User.objects.create_user(
        email="other@example.com",
        password="otherpassword123",
        full_name="Other User",
    )


@pytest.fixture
def api_client():
    from rest_framework.test import APIClient
    return APIClient()


@pytest.fixture
def auth_client(api_client, user):
    """API client authenticated as user."""
    from rest_framework_simplejwt.tokens import RefreshToken
    refresh = RefreshToken.for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return api_client


@pytest.fixture
def monitor(db, user):
    """A default monitor owned by user."""
    from monitors.models import Monitor
    return Monitor.objects.create(
        owner=user,
        name="Test Monitor",
        url="https://example.com",
        interval=60,
        timeout=10,
        expected_status_code=200,
        failure_threshold=3,
    )


@pytest.fixture
def monitor2(db, user2):
    """A monitor owned by user2 — for multitenancy tests."""
    from monitors.models import Monitor
    return Monitor.objects.create(
        owner=user2,
        name="User2's Monitor",
        url="https://other.com",
        interval=60,
        timeout=10,
    )
