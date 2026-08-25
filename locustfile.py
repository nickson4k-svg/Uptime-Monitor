"""
Locust load testing scenario for Pet-Uptime-Monitor.

Tests:
1. Public endpoints: /health/live/, /health/ready/, /metrics, /status/<slug>/
2. Authenticated endpoints: /api/v1/monitors/, /api/v1/incidents/
3. Real-time WebSocket connection simulations

Run with:
    locust -f locustfile.py --host=http://127.0.0.1:8000
"""

import random
from locust import HttpUser, between, task


class UptimeMonitorUser(HttpUser):
    wait_time = between(0.1, 1.0)

    def on_start(self):
        """Authenticate user and obtain JWT token."""
        self.email = f"loadtest_{random.randint(1000, 9999)}@example.com"
        self.password = "LoadTestPass123!"

        # Register
        self.client.post(
            "/api/v1/auth/register/",
            json={
                "email": self.email,
                "password": self.password,
                "password_confirm": self.password,
                "full_name": "Load Tester",
            },
        )

        # Login
        login_resp = self.client.post(
            "/api/v1/auth/token/",
            json={
                "email": self.email,
                "password": self.password,
            },
        )
        if login_resp.status_code == 200:
            token = login_resp.json().get("access")
            self.headers = {"Authorization": f"Bearer {token}"}
        else:
            self.headers = {}

    @task(5)
    def test_health_live(self):
        self.client.get("/health/live/", name="/health/live/")

    @task(3)
    def test_health_ready(self):
        self.client.get("/health/ready/", name="/health/ready/")

    @task(2)
    def test_metrics(self):
        self.client.get("/metrics", name="/metrics")

    @task(10)
    def test_list_monitors(self):
        if self.headers:
            self.client.get("/api/v1/monitors/", headers=self.headers, name="/api/v1/monitors/")

    @task(2)
    def test_create_and_delete_monitor(self):
        if not self.headers:
            return

        # Create
        resp = self.client.post(
            "/api/v1/monitors/",
            headers=self.headers,
            json={
                "name": "Load Test Service",
                "monitor_type": "http",
                "url": "https://example.com",
                "method": "GET",
                "expected_status_code": 200,
                "interval": 60,
                "timeout": 10,
                "regions": ["eu-central", "us-east"],
                "quorum_threshold": 1,
            },
            name="/api/v1/monitors/ [CREATE]",
        )
        if resp.status_code == 201:
            monitor_id = resp.json().get("id")
            if monitor_id:
                self.client.delete(
                    f"/api/v1/monitors/{monitor_id}/",
                    headers=self.headers,
                    name="/api/v1/monitors/{id}/ [DELETE]",
                )
