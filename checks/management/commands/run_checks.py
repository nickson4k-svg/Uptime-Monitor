from django.core.management.base import BaseCommand
from monitors.models import Monitor
from checks.tasks import check_monitor


class Command(BaseCommand):
    help = "Run checks on all active monitors immediately"

    def add_arguments(self, parser):
        parser.add_argument(
            "--monitor-id",
            type=int,
            help="Check a specific monitor by ID",
        )
        parser.add_argument(
            "--region",
            type=str,
            help="Force probe from a specific region (e.g. eu-central, us-east, ap-southeast)",
        )

    def handle(self, *args, **options):
        monitor_id = options.get("monitor_id")
        forced_region = options.get("region")

        if monitor_id:
            monitors = Monitor.objects.filter(pk=monitor_id, is_active=True)
        else:
            monitors = Monitor.objects.filter(is_active=True)

        if not monitors.exists():
            self.stdout.write(self.style.WARNING("No active monitors found to check."))
            return

        self.stdout.write(self.style.SUCCESS(f"Running multi-region checks for {monitors.count()} monitor(s)..."))
        for m in monitors:
            regions_to_check = [forced_region] if forced_region else m.get_regions()
            m_type = m.monitor_type.upper()
            for region in regions_to_check:
                res = check_monitor(m.id, region=region)
                status = res.get("status")
                ms = res.get("response_time_ms")
                code = res.get("http_code")
                if status == "up":
                    code_str = f" - {code} OK" if code else ""
                    self.stdout.write(
                        self.style.SUCCESS(f"  [UP]   [{m_type}] ({region}) {m.name} ({m.url}){code_str} ({ms}ms)")
                    )
                else:
                    self.stdout.write(
                        self.style.ERROR(f"  [DOWN] [{m_type}] ({region}) {m.name} ({m.url}) - Error: {res.get('error_type')}")
                    )
