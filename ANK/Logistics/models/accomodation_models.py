from django.db import models
from django.core.exceptions import ValidationError
import uuid
from Logistics.models.hotel_models import Hotel
from Guest.models import Guest
from Events.models.event_model import Event
from Events.models.session_registration import SessionRegistration
from Events.models.event_registration_model import EventRegistration, ExtraAttendee


class Accommodation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_id = models.ForeignKey(
        Event, on_delete=models.CASCADE, related_name="accommodations"
    )
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
    extra_attendee = models.ForeignKey(
        ExtraAttendee,
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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            # ensure either:
            # attendee is set (and we ignore the old registration fields), or
            # exactly one of the registration FKs is set
            models.CheckConstraint(
                check=(
                    models.Q(extra_attendee__isnull=False)
                    | (
                        models.Q(extra_attendee__isnull=True)
                        & (
                            models.Q(event_registration__isnull=False)
                            & models.Q(session_registration__isnull=True)
                        )
                        | (
                            models.Q(event_registration__isnull=True)
                            & models.Q(session_registration__isnull=False)
                        )
                    )
                ),
                name="accommodation_extraattendee_or_one_registration",
            )
        ]

    def clean(self):
        super().clean()
        # count how many of the three are truthy
        choices = [
            bool(self.event_registration),
            bool(self.session_registration),
            bool(self.extra_attendee),
        ]
        if sum(choices) != 1:
            raise ValidationError(
                "Exactly one of event_registration, session_registration or extra_attendee must be set."
            )

    def __str__(self):
        # pick whichever is set
        target = (
            self.extra_attendee or self.event_registration or self.session_registration
        )
        return f"Accommodation for {target}"
