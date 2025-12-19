import uuid
from django.db import models
from django.contrib.contenttypes.fields import GenericRelation
from Guest.models import Guest
from Events.models.event_model import Event


class EventRegistration(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    uid = models.CharField(max_length=50, unique=True, blank=True, null=True)
    guest = models.ForeignKey(Guest, on_delete=models.CASCADE)
    event = models.ForeignKey(
        Event, on_delete=models.CASCADE, related_name="registrations"
    )
    guest_group = models.CharField(max_length=20, blank=True, null=True)
    sub_guest_group = models.CharField(max_length=20, blank=True, null=True)
    name_on_message = models.CharField(max_length=200, blank=True, null=True)
    family_salutation = models.CharField(max_length=100, blank=True, null=True)
    title = models.CharField(max_length=20, blank=True, null=True)
    estimated_pax = models.PositiveIntegerField(default=1, blank=True, null=True)
    visa_oci = models.FileField(
        upload_to="guest_visas/",
        blank=True,
        null=True,
        help_text="Upload visa/OCI document",
    )
    hamper_count = models.PositiveIntegerField(default=0, blank=True, null=True)
    RSVP_CHOICES = [
        ("not_sent", "Not Sent"),
        ("pending", "Pending Response"),
        ("yes", "Yes"),
        ("no", "No"),
        ("maybe", "Maybe"),
    ]
    rsvp_status = models.CharField(
        max_length=10, choices=RSVP_CHOICES, default="not_sent"
    )
    initiated_on = models.DateTimeField(auto_now_add=True)
    responded_on = models.DateTimeField(null=True, blank=True)

    # Field to track how many extra attendees
    additional_guest_count = models.PositiveIntegerField(
        default=0, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # GenericRelation for custom field values
    custom_field_values = GenericRelation(
        'CustomField.CustomFieldValue',
        content_type_field='content_type',
        object_id_field='object_id',
        related_query_name='eventregistration'
    )

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
