from django.db import models
from django.core.exceptions import ValidationError
import uuid
from Events.models.event_model import Event
from Events.models.session_registration import SessionRegistration
from Events.models.event_registration_model import EventRegistration, ExtraAttendee


class TravelDetail(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(
        Event, on_delete=models.CASCADE, related_name="travel_details"
    )
    event_registrations = models.ManyToManyField(
        EventRegistration, blank=True, related_name="travel_detail_assignments"
    )
    extra_attendees = models.ManyToManyField(
        ExtraAttendee, blank=True, related_name="travel_detail_assignments"
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

    # --- Arrival fields ---
    arrival = models.CharField(max_length=20, choices=ARRIVAL_CHOICES)
    arrival_date = models.DateField()
    flight_number = models.CharField(max_length=20, blank=True)
    airline = models.CharField(max_length=50, blank=True)
    pnr = models.CharField(max_length=20, blank=True, null=True)
    arrival_details = models.TextField(blank=True)
    arrival_time = models.TimeField()
    hotel_arrival_time = models.TimeField(null=True, blank=True)
    hotel_departure_time = models.TimeField(null=True, blank=True)

    # --- Departure fields ---
    return_travel = models.BooleanField(default=False)
    departure = models.CharField(max_length=20, choices=DEPARTURE_CHOICES, blank=True)
    departure_date = models.DateField(null=True, blank=True)
    departure_details = models.TextField(blank=True)
    departure_flight_number = models.CharField(max_length=20, null=True, blank=True)
    departure_airline = models.CharField(max_length=50, null=True, blank=True)
    departure_pnr = models.CharField(max_length=20, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        super().clean()
        if not self.event_registrations.exists() and not self.extra_attendees.exists():
            raise ValidationError(
                "Travel detail must have at least one participant (EventRegistration or ExtraAttendee)."
            )

    def __str__(self):
        assigned = list(self.event_registrations.all()) + list(
            self.extra_attendees.all()
        )
        names = ", ".join(str(obj) for obj in assigned)
        return f"TravelDetail for: {names or 'No one'}"

    # class Meta:
    #     constraints = [
    #         # ensure either:
    #         # attendee is set (and we ignore the old registration fields), or
    #         # exactly one of the registration FKs is set
    #         models.CheckConstraint(
    #             check=(
    #                 models.Q(extra_attendee__isnull=False)
    #                 | (
    #                     models.Q(extra_attendee__isnull=True)
    #                     & (
    #                         models.Q(event_registration__isnull=False)
    #                         & models.Q(session_registration__isnull=True)
    #                     )
    #                     | (
    #                         models.Q(event_registration__isnull=True)
    #                         & models.Q(session_registration__isnull=False)
    #                     )
    #                 )
    #             ),
    #             name="travel_details_extraattendee_or_one_registration",
    #         )
    #     ]

    # def clean(self):
    #     super().clean()
    #     # count how many of the three are truthy
    #     choices = [
    #         bool(self.event_registration),
    #         bool(self.session_registration),
    #         bool(self.extra_attendee),
    #     ]
    #     if sum(choices) != 1:
    #         raise ValidationError(
    #             "Exactly one of event_registration, session_registration or extra_attendee must be set."
    #         )

    # def __str__(self):
    #     target = (
    #         self.extra_attendee or self.event_registration or self.session_registration
    #     )
    #     return f"Travel Details for {target}"


class TravelDetailField(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(
        max_length=50,
        unique=True,
        help_text="Exact field name on TravelDetail (e.g. 'location', 'venue')",
    )
    label = models.CharField(
        max_length=100, help_text="Human-readable label (e.g. 'Venue')"
    )

    def __str__(self):
        return self.label
