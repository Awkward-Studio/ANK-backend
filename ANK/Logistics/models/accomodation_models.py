from django.db import models
from django.core.exceptions import ValidationError
import uuid
from Logistics.models.hotel_models import Hotel
from Guest.models import Guest
from Events.models.session_registration import SessionRegistration
from Events.models.event_registration_model import EventRegistration


class Accommodation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_registration = models.ForeignKey(
        EventRegistration,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="accommodations",
    )
    session_registration = models.ForeignKey(
        SessionRegistration,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="accommodations",
    )
    hotel = models.ForeignKey(
        Hotel, on_delete=models.CASCADE, related_name="accommodations"
    )
    sharing_with = models.ForeignKey(
        Guest,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="shared_accommodations",
    )
    room_count = models.PositiveIntegerField(default=1)
    room_type = models.CharField(max_length=100)
    bed_type = models.CharField(max_length=100)
    check_in = models.DateTimeField()
    check_out = models.DateTimeField()
    rooming_remarks = models.TextField(blank=True)

    class Meta:
        constraints = [
            # enforce XOR: exactly one of the two must be non-null
            models.CheckConstraint(
                check=(
                    (
                        models.Q(event_registration__isnull=False)
                        & models.Q(session_registration__isnull=True)
                    )
                    | (
                        models.Q(event_registration__isnull=True)
                        & models.Q(session_registration__isnull=False)
                    )
                ),
                name="accommodation_one_registration_required",
            )
        ]

    def clean(self):
        super().clean()
        if not (self.event_registration ^ self.session_registration):
            raise ValidationError(
                "Set exactly one of event_registration or session_registration."
            )

    def __str__(self):
        booking = self.event_registration or self.session_registration
        return f"Accommodation for {booking}"
