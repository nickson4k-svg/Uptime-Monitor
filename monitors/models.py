"""
Monitor models.

Key architectural decisions:

1. MULTITENANCY via QuerySet:
   - MonitorQuerySet.for_user(user) filters by owner at DB level.
   - ALL views must call .for_user(request.user) — enforced by base ViewSet mixin.
   - Returns 404 (not 403) for resources belonging to other users — prevents enumeration.

2. consecutive_failures counter:
   - Stored on Monitor to avoid expensive COUNT query on CheckResult every time.
   - Incremented by Celery check task, reset to 0 on first UP.
   - When >= failure_threshold → Incident is opened.

3. current_status field:
   - Denormalized from last CheckResult for fast dashboard queries.
   - Updated atomically by check task (select_for_update recommended in high-concurrency).

4. public_slug:
   - Unique slug for public status page (/status/<slug>/).
   - Auto-generated from monitor name on first save if blank.
   - is_public=False means the slug still exists but page returns 404.
"""

import uuid

from django.conf import settings
from django.db import models
from django.utils.text import slugify


class Region(models.TextChoices):
    EU_CENTRAL = "eu-central", "Europe (Frankfurt)"
    US_EAST = "us-east", "US East (N. Virginia)"
    AP_SOUTHEAST = "ap-southeast", "Asia Pacific (Singapore)"


class MonitorType(models.TextChoices):
    HTTP = "http", "HTTP(s) Status"
    KEYWORD = "keyword", "Keyword / Content"
    SSL = "ssl", "SSL / TLS Certificate"
    TCP = "tcp", "TCP Port Ping"
    DOMAIN = "domain", "Domain Expiry"


class Method(models.TextChoices):
    GET = "GET", "GET"
    POST = "POST", "POST"
    HEAD = "HEAD", "HEAD"
    PUT = "PUT", "PUT"


class Interval(models.IntegerChoices):
    THIRTY_SECONDS = 30, "30 seconds"
    ONE_MINUTE = 60, "1 minute"
    FIVE_MINUTES = 300, "5 minutes"
    FIFTEEN_MINUTES = 900, "15 minutes"


class MonitorStatus(models.TextChoices):
    UNKNOWN = "unknown", "Unknown"
    UP = "up", "Up"
    DOWN = "down", "Down"
    PAUSED = "paused", "Paused"


class MonitorQuerySet(models.QuerySet):
    """Tenant-scoped QuerySet — always filter by owner."""

    def for_user(self, user) -> "MonitorQuerySet":
        """Return only monitors owned by this user."""
        return self.filter(owner=user)

    def active(self) -> "MonitorQuerySet":
        return self.filter(is_active=True)

    def public(self) -> "MonitorQuerySet":
        return self.filter(is_public=True)

    def by_interval(self, interval: int) -> "MonitorQuerySet":
        return self.filter(interval=interval)


class MonitorManager(models.Manager):
    def get_queryset(self) -> MonitorQuerySet:
        return MonitorQuerySet(self.model, using=self._db)

    def for_user(self, user) -> MonitorQuerySet:
        return self.get_queryset().for_user(user)


class Monitor(models.Model):
    """
    A monitor tracks the health of a service endpoint via multiple protocols.

    One Monitor → many CheckResults (append-only).
    One Monitor → at most one open Incident at a time.
    """

    # Owner reference — the core of multitenancy
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="monitors",
        db_index=True,
    )

    # Identity
    name = models.CharField(max_length=255)
    monitor_type = models.CharField(
        max_length=20,
        choices=MonitorType.choices,
        default=MonitorType.HTTP,
        db_index=True,
    )
    url = models.CharField(
        max_length=2000, help_text="Target URL or hostname / IP for TCP."
    )
    method = models.CharField(max_length=10, choices=Method.choices, default=Method.GET)

    # Multi-Region & Distributed Probing
    regions = models.JSONField(
        default=list,
        blank=True,
        help_text="List of region slugs (e.g. ['eu-central', 'us-east']). Empty defaults to ['eu-central'].",
    )
    quorum_threshold = models.PositiveSmallIntegerField(
        default=1,
        help_text="Number of regions that must concurrently report DOWN to open an incident.",
    )

    # Check parameters
    expected_status_code = models.PositiveSmallIntegerField(default=200)
    interval = models.PositiveIntegerField(
        choices=Interval.choices,
        default=Interval.ONE_MINUTE,
        db_index=True,  # indexed — used in fan-out dispatch query
    )
    timeout = models.PositiveSmallIntegerField(default=10)  # seconds
    request_body = models.TextField(blank=True)  # for POST monitors
    request_headers = models.JSONField(default=dict, blank=True)

    # Specific Checker configurations
    keyword = models.CharField(
        max_length=255,
        blank=True,
        help_text="Expected substring or regex on the target page (for KEYWORD check).",
    )
    keyword_should_exist = models.BooleanField(
        default=True,
        help_text="If True, monitor is DOWN if keyword is missing. If False, DOWN if keyword is present.",
    )
    tcp_port = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Target port for TCP ping check (e.g. 5432, 6379, 80).",
    )
    ssl_threshold_days = models.PositiveSmallIntegerField(
        default=14,
        help_text="Days remaining before SSL cert expiration to mark monitor DOWN/Warning.",
    )
    domain_threshold_days = models.PositiveSmallIntegerField(
        default=30,
        help_text="Days remaining before domain registration expiration to alert.",
    )

    # Status (denormalized for fast reads)
    current_status = models.CharField(
        max_length=10,
        choices=MonitorStatus.choices,
        default=MonitorStatus.UNKNOWN,
        db_index=True,
    )
    consecutive_failures = models.PositiveSmallIntegerField(default=0)
    last_checked_at = models.DateTimeField(null=True, blank=True)

    # Incident configuration
    failure_threshold = models.PositiveSmallIntegerField(
        default=3,
        help_text="Number of consecutive failures before opening an incident.",
    )

    # Lifecycle
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Public status page
    is_public = models.BooleanField(default=False)
    public_slug = models.SlugField(
        max_length=80,
        unique=True,
        blank=True,
        help_text="Used for /status/<slug>/ public page.",
    )

    objects = MonitorManager()

    class Meta:
        db_table = "monitors_monitor"
        ordering = ["-created_at"]
        indexes = [
            # Dispatch query: find all active monitors with a given interval
            models.Index(
                fields=["interval", "is_active"], name="idx_monitor_interval_active"
            ),
            # Owner + status — dashboard queries
            models.Index(
                fields=["owner", "current_status"], name="idx_monitor_owner_status"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.url})"

    def save(self, *args, **kwargs):
        if not self.public_slug:
            self.public_slug = self._generate_unique_slug()
        super().save(*args, **kwargs)

    def _generate_unique_slug(self) -> str:
        base = str(slugify(self.name)) or str(uuid.uuid4())[:8]
        slug = base
        counter = 1
        while Monitor.objects.filter(public_slug=slug).exists():
            slug = f"{base}-{counter}"
            counter += 1
        return str(slug)

    def get_regions(self) -> list[str]:
        """Return list of region codes to probe from (defaults to ['eu-central'])."""
        if self.regions and isinstance(self.regions, list) and len(self.regions) > 0:
            return self.regions
        return [Region.EU_CENTRAL.value]

    @property
    def is_down(self) -> bool:
        return self.current_status == MonitorStatus.DOWN

    @property
    def is_up(self) -> bool:
        return self.current_status == MonitorStatus.UP
