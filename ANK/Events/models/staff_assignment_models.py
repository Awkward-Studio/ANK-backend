import uuid
from django.db import models


from Events.models.event_model import Event
from Events.models.session_model import Session


class EventStaffAssignment(models.Model):
    ROLE_CHOICES = [
        ("lead", "Team Lead"),
        ("crew", "Crew Member"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        "Staff.User", on_delete=models.CASCADE, related_name="event_assignments"
    )
    event = models.ForeignKey(
        Event, on_delete=models.CASCADE, related_name="staff_assignments"
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    assigned_on = models.DateTimeField(auto_now_add=True)
    removed_on = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("user", "event")

    def __str__(self):
        return f"{self.user} as {self.role} on {self.event}"


class SessionStaffAssignment(models.Model):
    ROLE_CHOICES = [
        ("lead", "Session Lead"),
        ("crew", "Crew Member"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        "Staff.User", on_delete=models.CASCADE, related_name="session_assignments"
    )
    session = models.ForeignKey(
        Session, on_delete=models.CASCADE, related_name="staff_assignments"
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    assigned_on = models.DateTimeField(auto_now_add=True)
    removed_on = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("user", "session")

    def __str__(self):
        return f"{self.user} as {self.role} on {self.session}"
