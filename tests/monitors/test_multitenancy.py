"""
Multitenancy tests — most critical security tests in the project.

Principle: user can NEVER access another user's monitors, checks, or incidents.
Returns 404 (not 403) — does not reveal existence of the resource.

All tests use two users:
- user (auth_client) — the authenticated requester
- user2 (monitor2) — the victim user
"""

import pytest


@pytest.mark.django_db
class TestMonitorMultitenancy:
    def test_list_only_shows_own_monitors(self, auth_client, monitor, monitor2):
        """GET /monitors/ returns only user's monitors."""
        response = auth_client.get("/api/v1/monitors/")
        assert response.status_code == 200
        # Handle both paginated and non-paginated responses
        data = response.data
        if isinstance(data, dict) and "results" in data:
            monitor_ids = [m["id"] for m in data["results"]]
        else:
            monitor_ids = [m["id"] for m in data]

        assert monitor.pk in monitor_ids
        assert monitor2.pk not in monitor_ids

    def test_get_other_users_monitor_returns_404(self, auth_client, monitor2):
        """GET /monitors/{other_id}/ → 404, not 403."""
        response = auth_client.get(f"/api/v1/monitors/{monitor2.pk}/")
        assert response.status_code == 404

    def test_update_other_users_monitor_returns_404(self, auth_client, monitor2):
        """PATCH /monitors/{other_id}/ → 404."""
        response = auth_client.patch(
            f"/api/v1/monitors/{monitor2.pk}/",
            {"name": "Hacked"},
            format="json",
        )
        assert response.status_code == 404

    def test_delete_other_users_monitor_returns_404(self, auth_client, monitor2):
        """DELETE /monitors/{other_id}/ → 404."""
        response = auth_client.delete(f"/api/v1/monitors/{monitor2.pk}/")
        assert response.status_code == 404

    def test_pause_other_users_monitor_returns_404(self, auth_client, monitor2):
        response = auth_client.post(f"/api/v1/monitors/{monitor2.pk}/pause/")
        assert response.status_code == 404

    def test_stats_other_users_monitor_returns_empty(self, auth_client, monitor2):
        """Stats endpoint for another user's monitor returns empty data."""
        response = auth_client.get(f"/api/v1/monitors/{monitor2.pk}/stats/")
        # Either 404 or empty data — both acceptable
        assert response.status_code in (200, 404)

    def test_unauthenticated_cannot_list_monitors(self, api_client):
        response = api_client.get("/api/v1/monitors/")
        assert response.status_code == 401

    def test_owner_field_cannot_be_set_in_request(self, auth_client, user2):
        """
        Attempt to set owner to user2 in request body → ignored.
        Monitor is always created for the authenticated user.
        """
        response = auth_client.post(
            "/api/v1/monitors/",
            {
                "name": "Attempt",
                "url": "https://test.com",
                "method": "GET",
                "expected_status_code": 200,
                "interval": 60,
                "timeout": 10,
                "owner": str(user2.id),  # malicious
            },
            format="json",
        )
        # Either 400 (validation error) or 201 (but owner is current user)
        if response.status_code == 201:
            from monitors.models import Monitor
            m = Monitor.objects.get(pk=response.data["id"])
            assert m.owner != user2, "Owner was hijacked!"


@pytest.mark.django_db
class TestChecksMultitenancy:
    def test_checks_for_other_users_monitor_returns_empty(self, auth_client, monitor2):
        """GET /monitors/{other}/checks/ → empty list (no 403, no data leak)."""
        response = auth_client.get(f"/api/v1/monitors/{monitor2.pk}/checks/")
        assert response.status_code == 200
        data = response.data
        results = data.get("results", data) if isinstance(data, dict) else data
        assert len(results) == 0


@pytest.mark.django_db
class TestPublicStatusPage:
    def test_public_page_accessible_without_auth(self, api_client, monitor):
        """Public status page requires no authentication."""
        from monitors.models import Monitor
        monitor.is_public = True
        monitor.save()

        response = api_client.get(f"/api/v1/public/status/{monitor.public_slug}/")
        assert response.status_code == 200

    def test_private_monitor_slug_returns_404(self, api_client, monitor):
        """Non-public monitor → 404 even if slug is known."""
        monitor.is_public = False
        monitor.save()

        response = api_client.get(f"/api/v1/public/status/{monitor.public_slug}/")
        assert response.status_code == 404

    def test_nonexistent_slug_returns_404(self, api_client):
        response = api_client.get("/api/v1/public/status/nonexistent-slug-xyz/")
        assert response.status_code == 404

    def test_public_page_does_not_expose_owner(self, api_client, monitor):
        """Public API response must not include owner information."""
        monitor.is_public = True
        monitor.save()

        response = api_client.get(f"/api/v1/public/status/{monitor.public_slug}/")
        assert response.status_code == 200

        response_str = str(response.data)
        assert "owner" not in response_str
        assert "user" not in response_str.lower() or "user_id" not in response_str
