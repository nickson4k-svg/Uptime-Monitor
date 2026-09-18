"""
Django management command to manually or cron-prune raw check results older than N days.
"""

from django.core.management.base import BaseCommand

from checks.tasks import prune_old_checks


class Command(BaseCommand):
    help = "Prune raw CheckResult records older than N days (default 30 days)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=30,
            help="Number of days of raw telemetry to retain (default: 30)",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=5000,
            help="Batch size for chunked deletion (default: 5000)",
        )

    def handle(self, *args, **options):
        days = options["days"]
        batch_size = options["batch_size"]

        self.stdout.write(
            self.style.NOTICE(f"Pruning check results older than {days} days...")
        )
        count = prune_old_checks(days=days, batch_size=batch_size)
        self.stdout.write(
            self.style.SUCCESS(f"Successfully pruned {count} old check records.")
        )
