"""
Management command to seed rich, realistic demo data for presentations and portfolio showcases.
"""

from datetime import timedelta
import random
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from checks.models import CheckErrorType, CheckResult, CheckStatus, DailyStats, HourlyStats
from incidents.models import Incident
from monitors.models import Interval, Method, Monitor, MonitorStatus, MonitorType, Region

User = get_user_model()


class Command(BaseCommand):
    help = "Seed realistic demo monitors, historical telemetry, and incidents for portfolio demo."

    def add_arguments(self, parser):
        parser.add_argument(
            "--email",
            type=str,
            default="demo@example.com",
            help="Email address for the demo user (default: demo@example.com)",
        )
        parser.add_argument(
            "--password",
            type=str,
            default="DemoPassword123!",
            help="Password for the demo user (default: DemoPassword123!)",
        )

    def handle(self, *args, **options):
        email = options["email"]
        password = options["password"]

        self.stdout.write(self.style.NOTICE(f"Seeding demo workspace for user: {email}..."))

        # 1. Create or retrieve demo user
        user, created = User.objects.get_or_create(
            email=email,
            defaults={"full_name": "Demo Admin", "is_active": True},
        )
        user.set_password(password)
        user.save()

        # Clean existing monitors for this demo user to avoid duplicates
        Monitor.objects.filter(owner=user).delete()

        now = timezone.now()

        # 2. Monitor definitions across multiple protocols & regions
        demo_monitors_config = [
            {
                "name": "Stripe Payments Gateway",
                "monitor_type": MonitorType.HTTP,
                "url": "https://api.stripe.com/healthcheck",
                "method": Method.GET,
                "regions": [Region.EU_CENTRAL.value, Region.US_EAST.value],
                "quorum_threshold": 1,
                "interval": Interval.ONE_MINUTE,
                "status": MonitorStatus.UP,
                "is_public": True,
                "base_rt": 45,
            },
            {
                "name": "PostgreSQL Primary Cluster",
                "monitor_type": MonitorType.TCP,
                "url": "db.internal.production.net",
                "tcp_port": 5432,
                "regions": [Region.EU_CENTRAL.value],
                "quorum_threshold": 1,
                "interval": Interval.THIRTY_SECONDS,
                "status": MonitorStatus.UP,
                "is_public": False,
                "base_rt": 12,
            },
            {
                "name": "Redis In-Memory Session Cache",
                "monitor_type": MonitorType.TCP,
                "url": "redis.internal.production.net",
                "tcp_port": 6379,
                "regions": [Region.EU_CENTRAL.value, Region.US_EAST.value],
                "quorum_threshold": 1,
                "interval": Interval.THIRTY_SECONDS,
                "status": MonitorStatus.UP,
                "is_public": False,
                "base_rt": 4,
            },
            {
                "name": "Customer Identity & Auth Portal",
                "monitor_type": MonitorType.KEYWORD,
                "url": "https://auth.production.app/login",
                "method": Method.GET,
                "keyword": "Sign In to Your Workspace",
                "keyword_should_exist": True,
                "regions": [Region.EU_CENTRAL.value, Region.US_EAST.value, Region.AP_SOUTHEAST.value],
                "quorum_threshold": 2,
                "interval": Interval.ONE_MINUTE,
                "status": MonitorStatus.UP,
                "is_public": True,
                "base_rt": 78,
            },
            {
                "name": "Wildcard *.production.app TLS Certificate",
                "monitor_type": MonitorType.SSL,
                "url": "https://google.com",
                "ssl_threshold_days": 14,
                "regions": [Region.EU_CENTRAL.value],
                "quorum_threshold": 1,
                "interval": Interval.FIVE_MINUTES,
                "status": MonitorStatus.UP,
                "is_public": False,
                "base_rt": 35,
            },
            {
                "name": "Production Root Domain Registration",
                "monitor_type": MonitorType.DOMAIN,
                "url": "github.com",
                "domain_threshold_days": 30,
                "regions": [Region.EU_CENTRAL.value],
                "quorum_threshold": 1,
                "interval": Interval.FIFTEEN_MINUTES,
                "status": MonitorStatus.UP,
                "is_public": False,
                "base_rt": 120,
            },
            {
                "name": "Legacy Payment Gateway [DEGRADED]",
                "monitor_type": MonitorType.HTTP,
                "url": "https://httpstat.us/503",
                "method": Method.GET,
                "expected_status_code": 200,
                "regions": [Region.EU_CENTRAL.value, Region.US_EAST.value],
                "quorum_threshold": 1,
                "interval": Interval.ONE_MINUTE,
                "status": MonitorStatus.DOWN,
                "is_public": True,
                "base_rt": 450,
            },
        ]

        created_monitors = []
        for cfg in demo_monitors_config:
            base_rt = cfg.pop("base_rt")
            status = cfg.pop("status")
            m = Monitor.objects.create(
                owner=user,
                current_status=status,
                consecutive_failures=3 if status == MonitorStatus.DOWN else 0,
                last_checked_at=now,
                **cfg,
            )
            created_monitors.append((m, base_rt, status))

        # 3. Seed Hourly & Daily Telemetry Stats
        self.stdout.write("Generating 24 hours of hourly roll-up metrics...")
        for m, base_rt, status in created_monitors:
            # 24 Hours
            for h in range(24, 0, -1):
                hour_time = (now - timedelta(hours=h)).replace(minute=0, second=0, microsecond=0)
                is_currently_down = (status == MonitorStatus.DOWN) and (h <= 2)
                uptime = 0.0 if is_currently_down else (99.8 if random.random() > 0.9 else 100.0)
                total = 60
                up = int((uptime / 100.0) * total)
                avg_rt = max(1, int(base_rt + random.randint(-5, 15)))

                HourlyStats.objects.create(
                    monitor=m,
                    hour=hour_time,
                    total_checks=total,
                    up_checks=up,
                    avg_response_time_ms=avg_rt,
                    uptime_pct=uptime,
                )

            # 30 Days
            for d in range(30, 0, -1):
                day_date = (now - timedelta(days=d)).date()
                uptime = 100.0 if random.random() > 0.15 else round(random.uniform(98.5, 99.9), 2)
                total = 1440
                up = int((uptime / 100.0) * total)
                avg_rt = max(1, int(base_rt + random.randint(-4, 10)))

                DailyStats.objects.create(
                    monitor=m,
                    date=day_date,
                    total_checks=total,
                    up_checks=up,
                    avg_response_time_ms=avg_rt,
                    uptime_pct=uptime,
                    incident_count=1 if uptime < 99.0 else 0,
                )

        # 4. Seed Incident Records
        self.stdout.write("Generating demo incident history...")
        # Resolved incident yesterday on Auth Portal
        auth_monitor = created_monitors[3][0]
        Incident.objects.create(
            monitor=auth_monitor,
            failure_count=3,
            root_cause_error=CheckErrorType.KEYWORD_MISSING,
            root_cause_message="Outage confirmed by 2/3 regions (eu-central, us-east): Keyword 'Sign In to Your Workspace' was missing from DOM response",
            started_at=now - timedelta(hours=14),
            resolved_at=now - timedelta(hours=13, minutes=42),
            is_resolved=True,
            resolved_alert_sent=True,
        )

        # Active outage on Legacy Payment Gateway
        degraded_monitor = created_monitors[6][0]
        Incident.objects.create(
            monitor=degraded_monitor,
            failure_count=5,
            root_cause_error=CheckErrorType.HTTP_ERROR,
            root_cause_message="Outage confirmed by 2/2 regions (eu-central, us-east): Upstream gateway returned HTTP 503 Service Unavailable",
            started_at=now - timedelta(minutes=28),
            is_resolved=False,
            resolved_alert_sent=False,
        )

        self.stdout.write(self.style.SUCCESS("✓ Successfully seeded demo workspace!"))
        self.stdout.write(f"  User: {email}")
        self.stdout.write(f"  Password: {password}")
        self.stdout.write(f"  Monitors created: {len(created_monitors)}")
