from django.db import models
from django.core.exceptions import ValidationError
import uuid
from Logistics.models.hotel_models import EventHotel, EventHotelRoomType
from Guest.models import Guest
from Events.models.event_model import Event
from Events.models.session_registration import SessionRegistration
from Events.models.event_registration_model import EventRegistration, ExtraAttendee


class Accommodation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(
        Event, on_delete=models.CASCADE, related_name="accommodations"
    )
    event_registrations = models.ManyToManyField(
        EventRegistration, blank=True, related_name="accommodation_assignments"
    )
    extra_attendees = models.ManyToManyField(
        ExtraAttendee, blank=True, related_name="accommodation_assignments"
    )
    session_registration = models.ForeignKey(
        SessionRegistration,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="accommodations",
    )
    event_hotel = models.ForeignKey(
        EventHotel, on_delete=models.CASCADE, related_name="accommodations"
    )
    sharing_with = models.ForeignKey(
        Guest,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="shared_accommodations",
    )
    room_count = models.PositiveIntegerField(default=1)
    event_room_type = models.ForeignKey(
        EventHotelRoomType,
        on_delete=models.PROTECT,
        related_name="accommodations",
        null=True,
        blank=True,
    )
    bed_type = models.CharField(max_length=100)
    check_in = models.DateTimeField()
    check_out = models.DateTimeField()
    rooming_remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        super().clean()
        # Enforce at least one participant
        if not self.event_registrations.exists() and not self.extra_attendees.exists():
            raise ValidationError(
                "Accommodation must have at least one EventRegistration or ExtraAttendee assigned."
            )

    def __str__(self):
        assigned = list(self.event_registrations.all()) + list(
            self.extra_attendees.all()
        )
        names = ", ".join(str(obj) for obj in assigned)
        return f"Accommodation for: {names or 'No one'}"


class AccommodationField(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(
        max_length=50,
        unique=True,
        help_text="Exact field name on Accommodation (e.g. 'location', 'venue')",
    )
    label = models.CharField(
        max_length=100, help_text="Human-readable label (e.g. 'Venue')"
    )

    def __str__(self):
        return self.label
