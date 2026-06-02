from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from Events.models.event_model import Event
from Manpower.models import (
    AllocationDailyMeal,
    FreelancerAllocation,
    InvoiceWorkflow,
    MoU,
    PostEventAdjustment,
)


class Command(BaseCommand):
    help = (
        "Reset accepted manpower assignments for an event back to the accepted-MoU stage. "
        "Dry-runs by default; pass --apply to mutate data."
    )

    def add_arguments(self, parser):
        parser.add_argument("--event-id", required=True, help="Event UUID to reset.")
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Actually delete actuals/invoices and refresh daily meal rates.",
        )

    def handle(self, *args, **options):
        event_id = options["event_id"]
        apply = options["apply"]

        if not Event.objects.filter(id=event_id).exists():
            raise CommandError(f"Event {event_id} was not found.")

        allocations = (
            FreelancerAllocation.objects
            .filter(event_department__event_id=event_id, mous__status="accepted")
            .exclude(status="released")
            .select_related("freelancer", "event_department__event")
            .distinct()
            .order_by("freelancer__name", "created_at")
        )
        allocation_ids = list(allocations.values_list("id", flat=True))
        accepted_mous = MoU.objects.filter(allocation_id__in=allocation_ids, status="accepted")
        adjustments = PostEventAdjustment.objects.filter(allocation_id__in=allocation_ids)
        invoices = InvoiceWorkflow.objects.filter(adjustment__in=adjustments)
        meals = AllocationDailyMeal.objects.filter(allocation_id__in=allocation_ids)

        self.stdout.write(self.style.WARNING("Accepted-MoU manpower reset preview"))
        self.stdout.write(f"Event ID: {event_id}")
        self.stdout.write(f"Mode: {'APPLY' if apply else 'DRY RUN'}")
        self.stdout.write(f"Accepted allocations: {allocations.count()}")
        self.stdout.write(f"Accepted MoUs kept: {accepted_mous.count()}")
        self.stdout.write(f"Adjustments to delete: {adjustments.count()}")
        self.stdout.write(f"Invoices to delete via adjustment reset: {invoices.count()}")
        self.stdout.write(f"Daily meal rows to refresh from global rates: {meals.count()}")

        preview = list(allocations.values_list("freelancer__name", "id")[:100])
        if preview:
            self.stdout.write("Target allocations:")
            for freelancer_name, allocation_id in preview:
                self.stdout.write(f"  - {freelancer_name or 'Unknown'}: {allocation_id}")

        if not apply:
            self.stdout.write(self.style.SUCCESS("Dry run complete. Re-run with --apply to reset these rows."))
            return

        with transaction.atomic():
            for meal in meals.select_related("allocation"):
                meal.save()

            deleted_adjustments, deleted_breakdown = adjustments.delete()

            allocations.update(is_adjustment_editable=False)

        self.stdout.write(self.style.SUCCESS("Reset complete."))
        self.stdout.write(f"Deleted objects: {deleted_adjustments}")
        for model_label, count in sorted(deleted_breakdown.items()):
            self.stdout.write(f"  {model_label}: {count}")
        self.stdout.write("Accepted MoUs were not changed.")
