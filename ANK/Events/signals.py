import logging
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from Events.models.event_registration_model import (
    EventRegistration,
    ExtraAttendee,
)
from Events.models.event_model import Event
from Departments.models import Department, EventDepartment

logger = logging.getLogger(__name__)


def serialize_compact(er: EventRegistration) -> dict:
    """
    Compact payload for UI updates.
    Switch to `serialize_rsvp_only(er)` if you only want rsvp_status.
    """
    return {
        "id": str(er.id),
        "event": str(er.event_id),
        "guest": er.guest_id,
        "rsvp_status": er.rsvp_status,
        "estimated_pax": er.estimated_pax,
        "additional_guest_count": er.additional_guest_count,
        "responded_on": er.responded_on.isoformat() if er.responded_on else None,
        "updated_at": er.updated_at.isoformat() if er.updated_at else None,
    }


def serialize_rsvp_only(er: EventRegistration) -> dict:
    """Minimal payload if you only care about status."""
    return {
        "id": str(er.id),
        "event": str(er.event_id),
        "guest": er.guest_id,
        "rsvp_status": er.rsvp_status,
    }


@receiver(post_save, sender=EventRegistration)
def broadcast_rsvp_update(sender, instance: EventRegistration, created, **kwargs):
    """
    Broadcasts a message to group 'event_<event_id>' whenever an EventRegistration
    is created or updated. Runs AFTER COMMIT to avoid race conditions.
    """
    try:
        channel_layer = get_channel_layer()
        if channel_layer is None:
            logger.error("Channel layer is not configured. Skipping broadcast.")
            return

        # Decide what to send:
        body = serialize_compact(
            instance
        )  # <- change to serialize_rsvp_only(instance) if needed

        payload = {
            "type": "rsvp_update",  # must match consumer method
            "data": {
                "type": "rsvp_changed",
                "action": "created" if created else "updated",
                "registration": body,
            },
        }

        group_name = f"event_{instance.event_id}"

        # Ensure we only send after the DB transaction commits
        def _send():
            try:
                async_to_sync(channel_layer.group_send)(group_name, payload)
            except Exception:
                logger.exception("Failed to group_send RSVP update")

        transaction.on_commit(_send)

    except Exception:
        logger.exception("Error preparing RSVP broadcast")


@receiver(post_save, sender=EventRegistration)
def sync_extra_guests(sender, instance: EventRegistration, created, **kwargs):
    """
    Automatically synchronize the number of ExtraAttendee records 
    with the estimated_pax value.
    
    Logic:
    - estimated_pax includes the primary guest + extra guests
    - So if estimated_pax = 3, we need 2 extra guests (3 - 1 = 2)
    - Creates new ExtraAttendee records if count is too low
    - Deletes excess ExtraAttendee records if count is too high
    
    Runs after the DB transaction commits to ensure consistency.
    """
    def _sync_extras():
        try:
            # Refresh to get latest state after commit
            instance.refresh_from_db()
            
            # Calculate required number of extra guests
            # estimated_pax includes the primary guest, so subtract 1
            required_extras = max(0, instance.estimated_pax - 1)
            
            # Get current count of extra attendees
            current_extras = instance.extra_attendees.all()
            current_count = current_extras.count()
            
            # Calculate difference
            diff = required_extras - current_count
            
            if diff > 0:
                # Need to CREATE extra guests
                guest_name = instance.guest.name if instance.guest else "Guest"
                new_extras = [
                    ExtraAttendee(
                        registration=instance,
                        name=f"Guest of {guest_name} #{current_count + i + 1}",
                        phone="",
                    )
                    for i in range(diff)
                ]
                ExtraAttendee.objects.bulk_create(new_extras)
                logger.info(
                    f"[SYNC_EXTRAS] Created {diff} extra guests for registration {instance.id}. "
                    f"New total: {required_extras}"
                )
                
            elif diff < 0:
                # Need to DELETE extra guests (remove the last ones)
                to_delete_count = abs(diff)
                # Get the last N extra attendees (ordered by creation)
                to_delete = list(current_extras.order_by('-id')[:to_delete_count])
                deleted_ids = [str(ea.id) for ea in to_delete]
                
                # Delete them
                for ea in to_delete:
                    ea.delete()
                    
                logger.info(
                    f"[SYNC_EXTRAS] Deleted {to_delete_count} extra guests for registration {instance.id}. "
                    f"Deleted IDs: {deleted_ids}. New total: {required_extras}"
                )
            else:
                # No change needed
                logger.debug(
                    f"[SYNC_EXTRAS] No change needed for registration {instance.id}. "
                    f"Current extras: {current_count}, Required: {required_extras}"
                )
                
        except Exception:
            logger.exception(
                f"[SYNC_EXTRAS] Failed to sync extra guests for registration {instance.id}"
            )
    
    # Run after transaction commits to ensure all data is persisted
    transaction.on_commit(_sync_extras)


@receiver(post_save, sender=Event)
def create_event_departments(sender, instance: Event, created: bool, **kwargs):
    """
    When a new Event is created, create EventDepartment rows for all current Departments.
    Runs after the surrounding DB transaction commits to avoid race/PK issues.
    """
    if not created:
        return

    def _create_all_event_departments():
        # Keep memory small and queries fast
        deps = Department.objects.all().only("id", "name")
        rows = [
            EventDepartment(
                event=instance,
                department=d,
                # Optional: show a friendly name by default
                display_name=d.name,
            )
            for d in deps
        ]

        # unique_together(event, department) is enforced; this avoids IntegrityErrors
        # if another worker created the same rows concurrently.
        EventDepartment.objects.bulk_create(rows, ignore_conflicts=True)

    transaction.on_commit(_create_all_event_departments)
