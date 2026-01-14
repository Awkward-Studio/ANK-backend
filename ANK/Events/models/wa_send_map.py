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
    return timezone.now() + timedelta(days=4)


class WaSendMap(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Normalized phone without '+' (store digits only)
    wa_id = models.CharField(max_length=32, db_index=True)
    
    # Multi-number support: Track which of OUR numbers sent to this guest
    sender_phone_number_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        db_index=True,
        help_text="Which of OUR phone numbers sent to this guest (for reply routing)"
    )

    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="wa_send_maps",
        null=True,
        blank=True,
    )
    event_registration = models.ForeignKey(
        EventRegistration,
        on_delete=models.CASCADE,
        related_name="wa_send_maps",
        null=True,
        blank=True,
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
            # This ensures only ONE generic map exists per (WA ID, Sender, Registration, Flow Type).
            # Multi-number support: Include sender_phone_number_id for conversation isolation
            models.UniqueConstraint(
                fields=["wa_id", "sender_phone_number_id", "event_registration", "flow_type"],
                condition=Q(template_wamid__isnull=True, flow_type__isnull=False),
                name="unique_wa_sender_reg_flowtype",
            ),
        ]

    def __str__(self):
        return f"{self.wa_id} → {self.flow_type or 'Template'} → {self.event_registration_id}"
