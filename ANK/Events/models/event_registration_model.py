import uuid
from django.db import models
from Guest.models import Guest
from Events.models.event_model import Event


class EventRegistration(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    RSVP_CHOICES = [
        ("yes", "Yes"),
        ("no", "No"),
        ("maybe", "Maybe"),
        ("pending", "No Response"),
    ]
    guest = models.ForeignKey(Guest, on_delete=models.CASCADE)
    event = models.ForeignKey(
        Event, on_delete=models.CASCADE, related_name="registrations"
    )
    rsvp_status = models.CharField(
        max_length=10, choices=RSVP_CHOICES, default="pending"
    )
    initiated_on = models.DateTimeField(auto_now_add=True)
    responded_on = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("guest", "event")
        # ↑ ensures a given guest has exactly one RSVP row per Event

    def __str__(self):
        return f"{self.guest} → {self.event}: {self.rsvp_status}"
