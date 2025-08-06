import uuid
from django.db import models
from Guest.models import Guest
from Events.models.event_model import Event


class EventRegistration(models.Model):
    GROUPS = [
        ("family", "Family"),
        ("friends", "Friends"),
    ]
    SUB_GROUPS = [
        ("family", "Family"),
        ("school_friends", "School friends"),
        ("college_friends", "College friends"),
    ]
    TITLE_CHOICES = [
        ("mr", "Mr."),
        ("ms", "Ms."),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    guest = models.ForeignKey(Guest, on_delete=models.CASCADE)
    event = models.ForeignKey(
        Event, on_delete=models.CASCADE, related_name="registrations"
    )
    guest_group = models.CharField(max_length=20, choices=GROUPS, blank=True, null=True)
    sub_guest_group = models.CharField(
        max_length=20, choices=SUB_GROUPS, blank=True, null=True
    )

    name_on_message = models.CharField(max_length=200, blank=True, null=True)
    family_salutation = models.CharField(max_length=100, blank=True, null=True)
    title = models.CharField(max_length=5, choices=TITLE_CHOICES, blank=True, null=True)
    estimated_pax = models.PositiveIntegerField(default=1)
    visa_oci = models.FileField(
        upload_to="guest_visas/",
        blank=True,
        null=True,
        help_text="Upload visa/OCI document",
    )
    hamper_count = models.PositiveIntegerField(default=0)
    RSVP_CHOICES = [
        ("yes", "Yes"),
        ("no", "No"),
        ("maybe", "Maybe"),
        ("pending", "No Response"),
    ]
    rsvp_status = models.CharField(
        max_length=10, choices=RSVP_CHOICES, default="pending"
    )
    initiated_on = models.DateTimeField(auto_now_add=True)
    responded_on = models.DateTimeField(null=True, blank=True)

    # Field to track how many extra attendees
    additional_guest_count = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("guest", "event")
        # ↑ ensures a given guest has exactly one RSVP row per Event

    def __str__(self):
        return f"{self.guest} → {self.event}: {self.rsvp_status}"


class ExtraAttendee(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    registration = models.ForeignKey(
        EventRegistration, related_name="extra_attendees", on_delete=models.CASCADE
    )
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=20, blank=True)
    photo_id = models.FileField(upload_to="extra_attendee_ids/", blank=True, null=True)

    def __str__(self):
        return f"{self.name} (extra for {self.registration.guest})"


class EventRegistrationField(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(
        max_length=50,
        unique=True,
        help_text="Exact field name on EventRegistration (e.g. 'location', 'venue')",
    )
    label = models.CharField(
        max_length=100, help_text="Human-readable label (e.g. 'Venue')"
    )

    def __str__(self):
        return self.label
