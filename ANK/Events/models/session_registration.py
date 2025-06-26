import uuid
from django.db import models
from Guest.models import Guest
from Events.models.session_model import Session


class SessionRegistration(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    guest = models.ForeignKey(Guest, on_delete=models.CASCADE)
    session = models.ForeignKey(
        Session, on_delete=models.CASCADE, related_name="registrations"
    )
    registered_on = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("guest", "session")
        # ↑ prevents a guest signing up for the same Session twice

    def __str__(self):
        return f"{self.guest} in {self.session}"
