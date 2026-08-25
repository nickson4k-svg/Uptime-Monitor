"""
Unit tests for Security Hardening: SSRF protection, mass-assignment guards, and Rate Limiting.
"""

import pytest
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APIClient, APIRequestFactory

from accounts.views import AuthRateThrottle, CustomTokenObtainPairView
from monitors.serializers import MonitorSerializer


@pytest.mark.unit
class TestSSRFProtection:
    def test_ssrf_validator_rejects_loopback_and_private_ips(self):
        serializer = MonitorSerializer()

        # In non-debug mode, SSRF validator must reject private IP addresses
        with override_settings(DEBUG=False):
            with pytest.raises(Exception) as exc:
                serializer.validate_url("http://127.0.0.1:8080/admin")
            assert "Private/internal URLs are not allowed" in str(exc.value)

            with pytest.raises(Exception) as exc:
                serializer.validate_url("http://192.168.1.1/router")
            assert "Private/internal URLs are not allowed" in str(exc.value)

            with pytest.raises(Exception) as exc:
                serializer.validate_url("http://10.0.0.1/internal")
            assert "Private/internal URLs are not allowed" in str(exc.value)

            with pytest.raises(Exception) as exc:
                serializer.validate_url("http://169.254.169.254/latest/meta-data")
            assert "Private/internal URLs are not allowed" in str(exc.value)


@pytest.mark.django_db
class TestMassAssignmentProtection:
    def test_attacker_cannot_override_owner_or_consecutive_failures(self, user):
        client = APIClient()
        client.force_authenticate(user=user)

        payload = {
            "name": "Target Monitor",
            "url": "https://example.com",
            "owner": "99999",  # Attempt to assign to another user
            "consecutive_failures": 100,  # Read-only field
            "public_slug": "hacked-slug-123",  # Read-only field
        }

        response = client.post("/api/v1/monitors/", payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()

        # Verify owner is authentic user, not 99999
        assert data["name"] == "Target Monitor"
        assert data["consecutive_failures"] == 0
        assert data["public_slug"] != "hacked-slug-123"


@pytest.mark.unit
class TestAuthRateThrottling:
    def test_auth_throttle_blocks_excessive_requests(self, rf: APIRequestFactory):
        from django.contrib.auth.models import AnonymousUser

        class MockAuthThrottle(AuthRateThrottle):
            THROTTLE_RATES = {"auth": "2/minute"}

        throttle = MockAuthThrottle()
        request = rf.post("/api/v1/auth/token/")
        request.user = AnonymousUser()
        view = CustomTokenObtainPairView()

        # 1st request allowed
        assert throttle.allow_request(request, view) is True
        # 2nd request allowed
        assert throttle.allow_request(request, view) is True
        # 3rd request blocked by throttle
        assert throttle.allow_request(request, view) is False
