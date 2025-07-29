from django.db import models
from django.core.exceptions import ValidationError
import uuid
from Events.models.event_model import Event
from Events.models.session_registration import SessionRegistration
from Events.models.event_registration_model import EventRegistration, ExtraAttendee


class TravelDetail(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_id = models.ForeignKey(
        Event, on_delete=models.CASCADE, related_name="travel_details"
    )
    event_registration = models.ForeignKey(
        EventRegistration,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="travel_details",
    )
    session_registration = models.ForeignKey(
        SessionRegistration,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="travel_details",
    )
    extra_attendee = models.ForeignKey(
        ExtraAttendee,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="travel_details",
    )
    ARRIVAL_CHOICES = [
        ("commercial", "Commercial"),
        ("local_pickup", "Local Pickup"),
        ("self", "Self"),
    ]
    TRAVEL_TYPE_CHOICES = [
        ("Air", "Air"),
        ("Train", "Train"),
        ("Car", "Car"),
    ]
    DEPARTURE_CHOICES = ARRIVAL_CHOICES
    travel_type = models.CharField(
        max_length=20, choices=TRAVEL_TYPE_CHOICES, blank=True
    )
    arrival = models.CharField(max_length=20, choices=ARRIVAL_CHOICES)
    arrival_date = models.DateField()
    arrival_details = models.TextField(blank=True)
    arrival_time = models.TimeField()
    hotel_arrival_time = models.TimeField(null=True, blank=True)
    hotel_departure_time = models.TimeField(null=True, blank=True)

    return_travel = models.BooleanField(default=False)
    departure = models.CharField(max_length=20, choices=DEPARTURE_CHOICES, blank=True)
    departure_date = models.DateField(null=True, blank=True)
    departure_details = models.TextField(blank=True)

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
                name="travel_details_extraattendee_or_one_registration",
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
        target = (
            self.extra_attendee or self.event_registration or self.session_registration
        )
        return f"Travel Details for {target}"
