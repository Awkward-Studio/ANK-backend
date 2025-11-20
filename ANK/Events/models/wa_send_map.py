import uuid
from datetime import timedelta
from django.db import models
from django.utils import timezone
from Events.models.event_registration_model import EventRegistration
from Events.models.event_model import Event
from django.db.models import Q


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

    flow_type = models.CharField(
        max_length=32,
        blank=True,
        null=True,
        db_index=True,
        choices=(
            ("travel", "Travel Capture Flow"),
            ("rsvp", "RSVP Reply"),
        ),
    )

    expires_at = models.DateTimeField(default=default_expiry_30d)

    consumed_at = models.DateTimeField(blank=True, null=True, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["expires_at"]),
            models.Index(fields=["consumed_at"]),
        ]

        constraints = [
            # 1. Enforce uniqueness for template-based messages (template_wamid is unique)
            models.UniqueConstraint(
                fields=["template_wamid"],
                condition=Q(template_wamid__isnull=False),
                name="unique_template_wamid_check",
            ),
            # 2. Enforce uniqueness for generic (non-template) messages by flow type
            # This ensures only ONE generic map exists per (WA ID, Registration, Flow Type).
            models.UniqueConstraint(
                fields=["wa_id", "event_registration", "flow_type"],
                condition=Q(template_wamid__isnull=True, flow_type__isnull=False),
                name="unique_wa_reg_flowtype",
            ),
        ]

    def __str__(self):
        return f"{self.wa_id} → {self.flow_type or 'Template'} → {self.event_registration_id}"
