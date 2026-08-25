"""
Celery tasks for monitor checking and stats aggregation.

Architecture overview:
──────────────────────
Beat (4 fixed tasks)
  │
  ├── dispatch_checks(interval=30)   ─┐
  ├── dispatch_checks(interval=60)   ─┤  Fan-out via group()
  ├── dispatch_checks(interval=300)  ─┤     │
  └── dispatch_checks(interval=900)  ─┘     ▼
                                    N × check_monitor(monitor_id)
                                            │
                                    ┌───────┴──────────────┐
                                    │                      │
                              CheckResult.create()   IncidentService
                                    │                  .handle_check_result()
                              channel_layer                │
                              .group_send()          dispatch_notification.delay()
                                    │
                              WebSocket Consumer
                                    │
                              Browser Dashboard

Scaling note:
  At 10,000 monitors with 60s interval: dispatch_checks(60) runs once/minute,
  fetches 10k IDs in one query, creates group of 10k tasks → workers process
  in parallel. Beat CPU/memory stays constant regardless of monitor count.
"""

import logging
from datetime import timedelta

from asgiref.sync import async_to_sync
from celery import group, shared_task
from channels.layers import get_channel_layer
from django.db import transaction
from django.db.models import Avg, Count, Q
from django.utils import timezone

logger = logging.getLogger(__name__)


# ─── Fan-out Dispatch ─────────────────────────────────────────────────────────


@shared_task(name="checks.tasks.dispatch_checks", queue="checks", ignore_result=True)
def dispatch_checks(interval: int) -> None:
    """
    Dispatches check_monitor tasks for all active monitors with the given interval,
    fanning out across all assigned geographic regions.
    """
    from monitors.models import Monitor  # local import avoids circular deps

    monitors = list(
        Monitor.objects.filter(interval=interval, is_active=True).only("id", "regions")
    )

    if not monitors:
        logger.debug("No active monitors for interval=%ss", interval)
        return

    task_signatures = []
    for m in monitors:
        for region in m.get_regions():
            task_signatures.append(check_monitor.s(m.id, region=region))

    logger.info("Dispatching %d regional checks for interval=%ss across %d monitors", len(task_signatures), interval, len(monitors))

    # group() sends all tasks to the broker in a single pipeline operation
    check_group = group(task_signatures)
    check_group.apply_async()


# ─── Core Check Task ──────────────────────────────────────────────────────────


@shared_task(
    name="checks.tasks.check_monitor",
    bind=True,
    # No retries: better to miss one check than to create duplicate checks
    max_retries=0,
    time_limit=60,
    soft_time_limit=55,
    queue="checks",
    acks_late=True,
)
def check_monitor(self, monitor_id: int, region: str = "eu-central") -> dict:
    """
    Execute one health check probe for the given monitor from a specific region.
    """
    from checks.models import CheckResult
    from checks.services import MonitorChecker
    from incidents.services import IncidentService
    from monitors.models import Monitor

    try:
        monitor_data = Monitor.objects.filter(pk=monitor_id, is_active=True).values(
            "id",
            "monitor_type",
            "url",
            "method",
            "timeout",
            "expected_status_code",
            "request_headers",
            "request_body",
            "keyword",
            "keyword_should_exist",
            "tcp_port",
            "ssl_threshold_days",
            "domain_threshold_days",
            "owner_id",
            "failure_threshold",
            "quorum_threshold",
            "regions",
        ).first()
    except Exception:
        logger.exception("Failed to load monitor %s", monitor_id)
        return {"error": "db_error", "monitor_id": monitor_id, "region": region}

    if monitor_data is None:
        logger.info("Monitor %s not found or inactive — skipping", monitor_id)
        return {"skipped": True, "monitor_id": monitor_id, "region": region}

    # ── Step 1: Execute Protocol Check (Strategy Pattern) ─────────────────────
    checker = MonitorChecker(monitor_data)
    result = checker.run()

    logger.info(
        "Monitor %s [%s] (%s) → %s (http=%s, ms=%s, error=%s)",
        monitor_id,
        monitor_data.get("monitor_type", "http"),
        region,
        result.status,
        result.http_code,
        result.response_time_ms,
        result.error_type if result.is_down else "-",
    )

    # ── Step 2: Persist CheckResult ──────────────────────────────────────────
    now = timezone.now()
    check_result = CheckResult.objects.create(
        monitor_id=monitor_id,
        region=region,
        checked_at=now,
        status=result.status,
        response_time_ms=result.response_time_ms,
        http_code=result.http_code,
        error_type=result.error_type,
        error_message=result.error_message,
    )

    # Update last_checked_at on Monitor
    Monitor.objects.filter(pk=monitor_id).update(last_checked_at=now)

    # ── Step 4: Record Prometheus Metrics ─────────────────────────────────────
    try:
        from config.metrics import UPTIME_CHECKS_TOTAL, UPTIME_CHECK_DURATION_SECONDS
        m_type = monitor_data.get("monitor_type", "http")
        UPTIME_CHECKS_TOTAL.labels(monitor_type=m_type, region=region, status=result.status).inc()
        if result.response_time_ms is not None:
            UPTIME_CHECK_DURATION_SECONDS.labels(monitor_type=m_type, region=region).observe(result.response_time_ms / 1000.0)
    except Exception:
        pass

    # ── Step 5: Push live event to WebSocket clients ──────────────────────────
    _push_status_event(
        owner_id=str(monitor_data["owner_id"]),
        monitor_id=monitor_id,
        status=result.status,
        response_time_ms=result.response_time_ms,
        http_code=result.http_code,
        region=region,
        checked_at=now.isoformat(),
    )

    return {
        "monitor_id": monitor_id,
        "region": region,
        "status": result.status,
        "response_time_ms": result.response_time_ms,
        "http_code": result.http_code,
        "error_type": result.error_type,
        "check_result_id": check_result.pk,
    }


def _push_status_event(
    owner_id: str,
    monitor_id: int,
    status: str,
    response_time_ms,
    http_code,
    region: str,
    checked_at: str,
) -> None:
    """
    Send a real-time status update to all WebSocket clients of the monitor's owner.
    """
    try:
        channel_layer = get_channel_layer()
        group_name = f"monitor_updates_{owner_id}"

        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                "type": "monitor.status_update",
                "monitor_id": monitor_id,
                "status": status,
                "response_time_ms": response_time_ms,
                "http_code": http_code,
                "region": region,
                "checked_at": checked_at,
            },
        )
    except Exception:
        logger.exception("Failed to push WebSocket event for monitor %s", monitor_id)



# ─── Aggregation Tasks ────────────────────────────────────────────────────────


@shared_task(name="checks.tasks.aggregate_hourly_stats", queue="checks", ignore_result=True)
def aggregate_hourly_stats() -> None:
    """
    Aggregate CheckResult rows from the previous completed hour into HourlyStats.

    Runs at :05 every hour (to ensure the hour's checks are complete).
    Uses get_or_create to be idempotent — safe to re-run.
    """
    from checks.models import CheckResult, CheckStatus, HourlyStats
    from monitors.models import Monitor

    # Previous completed hour
    now = timezone.now()
    hour_start = (now - timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    hour_end = hour_start + timedelta(hours=1)

    monitor_ids = Monitor.objects.filter(is_active=True).values_list("id", flat=True)
    count = 0

    for monitor_id in monitor_ids:
        results = CheckResult.objects.filter(
            monitor_id=monitor_id,
            checked_at__gte=hour_start,
            checked_at__lt=hour_end,
        )
        aggregated = results.aggregate(
            total=Count("id"),
            up_count=Count("id", filter=Q(status=CheckStatus.UP)),
            avg_rt=Avg("response_time_ms"),
        )

        if aggregated["total"] == 0:
            continue  # No checks in this hour for this monitor

        uptime_pct = (
            round((aggregated["up_count"] / aggregated["total"]) * 100, 2)
            if aggregated["total"] > 0
            else None
        )

        HourlyStats.objects.update_or_create(
            monitor_id=monitor_id,
            hour=hour_start,
            defaults={
                "total_checks": aggregated["total"],
                "up_checks": aggregated["up_count"],
                "avg_response_time_ms": int(aggregated["avg_rt"]) if aggregated["avg_rt"] else None,
                "uptime_pct": uptime_pct,
            },
        )
        count += 1

    logger.info("Aggregated hourly stats for %d monitors (hour=%s)", count, hour_start)


@shared_task(name="checks.tasks.aggregate_daily_stats", queue="checks", ignore_result=True)
def aggregate_daily_stats() -> None:
    """
    Roll up yesterday's HourlyStats into DailyStats.
    Runs at 00:10 UTC daily.
    """
    from checks.models import DailyStats, HourlyStats
    from monitors.models import Monitor

    yesterday = (timezone.now() - timedelta(days=1)).date()
    monitor_ids = Monitor.objects.filter(is_active=True).values_list("id", flat=True)
    count = 0

    for monitor_id in monitor_ids:
        hourly = HourlyStats.objects.filter(
            monitor_id=monitor_id,
            hour__date=yesterday,
        ).aggregate(
            total=Count("total_checks"),
            up=Count("up_checks"),
            avg_rt=Avg("avg_response_time_ms"),
        )

        # More accurate: sum from individual hourly rows
        from django.db.models import Sum
        hourly_sum = HourlyStats.objects.filter(
            monitor_id=monitor_id,
            hour__date=yesterday,
        ).aggregate(
            total=Sum("total_checks"),
            up=Sum("up_checks"),
            avg_rt=Avg("avg_response_time_ms"),
        )

        total = hourly_sum["total"] or 0
        if total == 0:
            continue

        up = hourly_sum["up"] or 0
        uptime_pct = round((up / total) * 100, 2)

        # Count incidents for that day
        from incidents.models import Incident
        incident_count = Incident.objects.filter(
            monitor_id=monitor_id,
            started_at__date=yesterday,
        ).count()

        DailyStats.objects.update_or_create(
            monitor_id=monitor_id,
            date=yesterday,
            defaults={
                "total_checks": total,
                "up_checks": up,
                "avg_response_time_ms": int(hourly_sum["avg_rt"]) if hourly_sum["avg_rt"] else None,
                "uptime_pct": uptime_pct,
                "incident_count": incident_count,
            },
        )
        count += 1

    logger.info("Aggregated daily stats for %d monitors (date=%s)", count, yesterday)


@shared_task(name="checks.tasks.prune_old_checks", queue="checks", ignore_result=True)
def prune_old_checks(days: int = 30, batch_size: int = 5000) -> int:
    """
    Prunes raw CheckResult records older than `days` in chunked batches.
    Long-term metrics remain preserved in HourlyStats and DailyStats.
    """
    from checks.models import CheckResult

    cutoff = timezone.now() - timedelta(days=days)
    total_deleted = 0

    while True:
        # Fetch IDs in batches to avoid locking the entire table
        ids_to_delete = list(
            CheckResult.objects.filter(checked_at__lt=cutoff)
            .values_list("id", flat=True)[:batch_size]
        )
        if not ids_to_delete:
            break

        deleted_count, _ = CheckResult.objects.filter(id__in=ids_to_delete).delete()
        total_deleted += deleted_count
        logger.info("Pruned batch of %d raw check results (total so far: %d)", deleted_count, total_deleted)

    logger.info("Pruned a total of %d raw CheckResult records older than %d days", total_deleted, days)
    return total_deleted

