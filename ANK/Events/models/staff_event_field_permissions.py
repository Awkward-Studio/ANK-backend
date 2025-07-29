# events/models/field_permissions.py

from django.db import models
from django.conf import settings
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
