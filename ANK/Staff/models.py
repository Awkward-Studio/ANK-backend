import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser
from Guest.models import GuestField
from Events.models.event_model import Event
from Events.models.session_model import Session


class User(AbstractUser):
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]
    # username, email, password, etc. all come from AbstractUser
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, blank=True)
    email = models.EmailField(unique=True, blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)

    ROLE_CHOICES = [
        ("admin", "Admin"),  # can assign staff
        ("staff", "Staff"),  # regular operational user
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

    # grant access to some subset of Events / Sessions
    assigned_events = models.ManyToManyField(
        Event, blank=True, related_name="staff_users"
    )
    assigned_sessions = models.ManyToManyField(
        Session, blank=True, related_name="staff_users"
    )

    # guest-related fields that staff can manage
    allowed_guest_fields = models.ManyToManyField(
        GuestField,
        blank=True,
        help_text="Which Guest fields this user may view",
        related_name="allowed_fields_staff",
    )

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
