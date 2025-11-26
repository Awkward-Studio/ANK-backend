import uuid
from django.db import models


class Guest(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    nationality = models.CharField(max_length=100, blank=True, null=True) 
    photo_id = models.ImageField(
        upload_to="guest_photo_ids/",
        blank=True,
        help_text="Scan or photo of guest ID (Visa/OCI etc.)",
        null=True
    )

    # “Through” tables handle RSVPs & registrations...
    events = models.ManyToManyField(
        "Events.Event", through="Events.EventRegistration", related_name="guests"
    )
    sessions = models.ManyToManyField(
        "Events.Session", through="Events.SessionRegistration", related_name="guests"
    )

    def __str__(self):
        return self.name


class GuestField(models.Model):
    # A list of all possible fields that are going to be exposed
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(
        max_length=50,
        unique=True,
        help_text="Exact field name on Guest (e.g. 'email', 'address')",
    )
    label = models.CharField(
        max_length=100, help_text="Human-readable (e.g. 'Email Address')"
    )

    def __str__(self):
        return self.label
