from django.db import models
from django.conf import settings
from Events.models.event_registration_model import EventRegistrationField
from Logistics.models.accomodation_models import AccommodationField
from Logistics.models.travel_details_models import TravelDetailField
from Events.models.event_model import Event, EventField
from Events.models.session_model import SessionField
from Guest.models import GuestField


class UserEventFieldPermission(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    event_field = models.ForeignKey(EventField, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("user", "event", "event_field")


class UserEventGuestFieldPermission(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    guest_field = models.ForeignKey(GuestField, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("user", "event", "guest_field")


class UserEventSessionFieldPermission(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    session_field = models.ForeignKey(SessionField, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("user", "event", "session_field")


class UserEventTravelDetailFieldPermission(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    traveldetail_field = models.ForeignKey(TravelDetailField, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("user", "event", "traveldetail_field")


class UserEventEventRegistrationFieldPermission(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    eventregistration_field = models.ForeignKey(
        EventRegistrationField, on_delete=models.CASCADE
    )

    class Meta:
        unique_together = ("user", "event", "eventregistration_field")


class UserEventAccommodationFieldPermission(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    accommodation_field = models.ForeignKey(
        AccommodationField, on_delete=models.CASCADE
    )

    class Meta:
        unique_together = ("user", "event", "accommodation_field")
