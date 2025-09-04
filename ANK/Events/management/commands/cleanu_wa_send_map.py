from django.core.management.base import BaseCommand
from django.utils import timezone
from Events.models.wa_send_map import WaSendMap
from django.db import models


class Command(BaseCommand):
    help = "Delete expired or consumed WaSendMap rows."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true", help="Do not delete, just report."
        )

    def handle(self, *args, **opts):
        now = timezone.now()
        qs = WaSendMap.objects.filter(
            models.Q(consumed_at__isnull=False) | models.Q(expires_at__lt=now)
        )
        count = qs.count()
        if opts["dry_run"]:
            self.stdout.write(self.style.WARNING(f"[DRY] Would delete {count} rows"))
            return
        qs.delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {count} WaSendMap rows"))
