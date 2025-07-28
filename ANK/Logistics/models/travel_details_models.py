from django.db import models
from django.core.exceptions import ValidationError
import uuid
from Events.models.event_model import Event
from Events.models.session_registration import SessionRegistration
from Events.models.event_registration_model import EventRegistration


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
                name="travel_one_registration_required",
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
        return f"Travel for {booking}"
