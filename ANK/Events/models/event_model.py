import uuid
from django.db import models
from django.contrib.contenttypes.fields import GenericRelation
from CustomField.models import CustomFieldValue


class Event(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    location = models.CharField(max_length=200, blank=True, null=True)
    venue = models.CharField(max_length=200, blank=True, null=True)
    start_date = models.DateField(db_index=True, blank=True, null=True)
    end_date = models.DateField(db_index=True, blank=True, null=True)
    pax = models.PositiveIntegerField(
        default=0, help_text="Expected number of attendees"
    )
    bride_name = models.CharField(max_length=200, blank=True, null=True)
    groom_name = models.CharField(max_length=200, blank=True, null=True)
    # allow querying event.custom_field_values
    custom_field_values = GenericRelation(
        CustomFieldValue,
        content_type_field="content_type",
        object_id_field="object_id",
    )

    def __str__(self):
        return f"{self.name} ({self.start_date:%Y-%m-%d}–{self.end_date:%Y-%m-%d})"


class EventField(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(
        max_length=50,
        unique=True,
        help_text="Exact field name on Event (e.g. 'location', 'venue')",
    )
    label = models.CharField(
        max_length=100, help_text="Human-readable label (e.g. 'Venue')"
    )

    def __str__(self):
        return self.label
