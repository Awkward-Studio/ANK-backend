from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from Departments.models import Department, EventDepartment
from Events.models.event_model import Event


@receiver(post_save, sender=Department)
def create_missing_event_departments_for_new_department(
    sender, instance: Department, created: bool, **kwargs
):
    if not created:
        return

    def _backfill_for_all_events():
        events = Event.objects.all().only("id", "name")
        rows = [
            EventDepartment(event=e, department=instance, display_name=instance.name)
            for e in events
        ]
        EventDepartment.objects.bulk_create(rows, ignore_conflicts=True)

    transaction.on_commit(_backfill_for_all_events)
