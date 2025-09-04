import uuid
from datetime import timedelta
from django.db import models
from django.utils import timezone
from Events.models.event_registration_model import EventRegistration
from Events.models.event_model import Event


def default_expiry_30d():
    """
    Return a timezone-aware datetime 30 days from now.
    Must be a top-level function so Django can serialize it in migrations.
    """
    return timezone.now() + timedelta(days=30)


class WaSendMap(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Normalized phone without '+' (store digits only)
    wa_id = models.CharField(max_length=32, db_index=True)

    event = models.ForeignKey(
        Event, on_delete=models.CASCADE, related_name="wa_send_maps"
    )
    event_registration = models.ForeignKey(
        EventRegistration, on_delete=models.CASCADE, related_name="wa_send_maps"
    )

    template_wamid = models.CharField(
        max_length=128, blank=True, null=True, unique=True
    )

    expires_at = models.DateTimeField(default=default_expiry_30d)

    consumed_at = models.DateTimeField(blank=True, null=True, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["wa_id", "event"]),
            models.Index(fields=["expires_at"]),
            models.Index(fields=["consumed_at"]),
        ]

    def __str__(self):
        return f"{self.wa_id} → {self.event_id} → {self.event_registration_id}"
