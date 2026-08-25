"""
Check models: raw time-series + aggregated stats.

Design decisions:

1. CheckResult is APPEND-ONLY:
   - Never UPDATE or DELETE individual rows (except TTL cleanup).
   - Composite index on (monitor_id, checked_at DESC) covers all time-range queries.
   - No FK to User — join happens through Monitor when needed.

2. HourlyStats / DailyStats:
   - Pre-aggregated by Celery task every hour / day.
   - Uptime% for dashboard is O(24) or O(30) rows, not O(millions).
   - unique_together prevents duplicate aggregation windows.
   - NULL avg_response_time_ms when all checks in window failed.

3. CheckErrorType enum:
   - Structured error classification, not freeform strings.
   - Enables future "most common failure reason" analytics.
"""

from django.db import models
from django.utils import timezone

from monitors.models import Monitor


class CheckStatus(models.TextChoices):
    UP = "up", "Up"
    DOWN = "down", "Down"


class CheckErrorType(models.TextChoices):
    NONE = "none", "None"
    TIMEOUT = "timeout", "Timeout"
    CONNECTION_ERROR = "connection_error", "Connection Error"
    DNS_ERROR = "dns_error", "DNS Resolution Error"
    SSL_ERROR = "ssl_error", "SSL/TLS Error"
    HTTP_ERROR = "http_error", "Unexpected HTTP Status"
    TOO_MANY_REDIRECTS = "too_many_redirects", "Too Many Redirects"
    KEYWORD_MISSING = "keyword_missing", "Keyword Missing"
    KEYWORD_PRESENT = "keyword_present", "Forbidden Keyword Found"
    SSL_EXPIRING_SOON = "ssl_expiring_soon", "SSL Certificate Expiring Soon"
    SSL_EXPIRED = "ssl_expired", "SSL Certificate Expired"
    DOMAIN_EXPIRING_SOON = "domain_expiring_soon", "Domain Expiring Soon"
    DOMAIN_EXPIRED = "domain_expired", "Domain Registration Expired"
    TCP_CONNECTION_FAILED = "tcp_connection_failed", "TCP Port Connection Failed"
    UNKNOWN = "unknown", "Unknown Error"


class CheckResult(models.Model):
    """
    Raw check result — one row per monitor ping.
    Append-only: never updated after insert.
    """

    monitor = models.ForeignKey(
        Monitor,
        on_delete=models.CASCADE,
        related_name="check_results",
        db_index=False,  # index is on composite below
    )
    region = models.CharField(max_length=32, default="eu-central", db_index=True)
    checked_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=10, choices=CheckStatus.choices)
    response_time_ms = models.PositiveIntegerField(null=True, blank=True)
    http_code = models.PositiveSmallIntegerField(null=True, blank=True)
    error_type = models.CharField(
        max_length=30,
        choices=CheckErrorType.choices,
        default=CheckErrorType.NONE,
    )
    error_message = models.TextField(blank=True)

    class Meta:
        db_table = "checks_checkresult"
        # Default ordering — most recent first
        ordering = ["-checked_at"]
        indexes = [
            # Primary access pattern: monitor's recent history for graph/stats
            models.Index(fields=["monitor", "-checked_at"], name="idx_checkresult_monitor_time"),
            # Multi-region access pattern: monitor's recent history per region
            models.Index(fields=["monitor", "region", "-checked_at"], name="idx_checkresult_mon_reg_time"),
            # Aggregation: find all results in a time window
            models.Index(fields=["checked_at"], name="idx_checkresult_time"),
        ]

    def __str__(self) -> str:
        return f"{self.monitor_id} @ {self.checked_at}: {self.status}"


class HourlyStats(models.Model):
    """
    Hourly aggregation of CheckResult rows.
    Computed by aggregate_hourly_stats Celery task.
    Covers the completed hour: [hour, hour+1h).
    """

    monitor = models.ForeignKey(
        Monitor,
        on_delete=models.CASCADE,
        related_name="hourly_stats",
    )
    # Truncated to the start of the hour (UTC)
    hour = models.DateTimeField(db_index=True)
    total_checks = models.PositiveIntegerField(default=0)
    up_checks = models.PositiveIntegerField(default=0)
    avg_response_time_ms = models.PositiveIntegerField(null=True, blank=True)
    # Stored as decimal for precision (e.g., 99.93%)
    uptime_pct = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )

    class Meta:
        db_table = "checks_hourlystats"
        unique_together = [("monitor", "hour")]
        indexes = [
            models.Index(fields=["monitor", "-hour"], name="idx_hourlystats_monitor_hour"),
        ]

    def __str__(self) -> str:
        return f"{self.monitor_id} @ {self.hour}: {self.uptime_pct}% up"


class DailyStats(models.Model):
    """
    Daily aggregation. Rolled up from HourlyStats by aggregate_daily_stats task.
    Used for 7d / 30d uptime charts.
    """

    monitor = models.ForeignKey(
        Monitor,
        on_delete=models.CASCADE,
        related_name="daily_stats",
    )
    # Date only (stored as DateField for clean GROUP BY)
    date = models.DateField(db_index=True)
    total_checks = models.PositiveIntegerField(default=0)
    up_checks = models.PositiveIntegerField(default=0)
    avg_response_time_ms = models.PositiveIntegerField(null=True, blank=True)
    uptime_pct = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    # Track incidents that day
    incident_count = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = "checks_dailystats"
        unique_together = [("monitor", "date")]
        indexes = [
            models.Index(fields=["monitor", "-date"], name="idx_dailystats_monitor_date"),
        ]

    def __str__(self) -> str:
        return f"{self.monitor_id} @ {self.date}: {self.uptime_pct}% up"
