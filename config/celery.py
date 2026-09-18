"""
Celery application configuration.

Key decisions:
- autodiscover_tasks() scans all LOCAL_APPS for tasks.py files
- Beat schedule for fan-out dispatch tasks (4 fixed tasks, not one per monitor)
- Separate queues: 'checks' for pinging, 'notifications' for alerting
"""

import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

app = Celery("uptime_monitor")

# Load configuration from Django settings (CELERY_* prefix)
app.config_from_object("django.conf:settings", namespace="CELERY")

# Autodiscover tasks in all Django apps
app.autodiscover_tasks()


# ─── Beat Schedule ────────────────────────────────────────────────────────────
# Fan-out strategy: 4 fixed periodic tasks dispatch to N workers.
# Beat does NOT know about individual monitors — only about intervals.
# This scales to thousands of monitors without touching Beat's schedule.
#
# Each dispatch_checks_{interval} task:
#   1. Queries Monitor.objects.filter(interval=X, is_active=True)
#   2. Creates a Celery group(check_monitor.s(id) for id in ids)
#   3. Applies the group — workers pick up individual check tasks
#
# Aggregation tasks run less frequently to roll up raw CheckResult rows
# into HourlyStats / DailyStats for efficient uptime% calculation.
app.conf.beat_schedule = {
    # Monitor dispatch (fan-out)
    "dispatch-checks-30s": {
        "task": "checks.tasks.dispatch_checks",
        "schedule": 30.0,
        "args": [30],
        "options": {"queue": "checks"},
    },
    "dispatch-checks-60s": {
        "task": "checks.tasks.dispatch_checks",
        "schedule": 60.0,
        "args": [60],
        "options": {"queue": "checks"},
    },
    "dispatch-checks-5m": {
        "task": "checks.tasks.dispatch_checks",
        "schedule": 300.0,
        "args": [300],
        "options": {"queue": "checks"},
    },
    "dispatch-checks-15m": {
        "task": "checks.tasks.dispatch_checks",
        "schedule": 900.0,
        "args": [900],
        "options": {"queue": "checks"},
    },
    # Aggregation (runs every hour at :05 to avoid overlap with dispatch)
    "aggregate-hourly-stats": {
        "task": "checks.tasks.aggregate_hourly_stats",
        "schedule": crontab(minute=5),
        "options": {"queue": "checks"},
    },
    # Daily aggregation at 00:10 UTC
    "aggregate-daily-stats": {
        "task": "checks.tasks.aggregate_daily_stats",
        "schedule": crontab(hour=0, minute=10),
        "options": {"queue": "checks"},
    },
}


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
