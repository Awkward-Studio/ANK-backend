import uuid
from django.db import models
from django.contrib.contenttypes.fields import GenericRelation
from Logistics.models.hotel_models import Hotel
from Events.models.event_model import Event


class Session(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, related_name="sessions", on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    description = models.TextField(max_length=1000, blank=True, null=True)
    start_time = models.DateTimeField(db_index=True, blank=True, null=True)
    end_time = models.DateTimeField(db_index=True, blank=True, null=True)
    pax = models.PositiveIntegerField(
        default=0, help_text="Expected number of attendees in this session"
    )
    date = models.DateField(db_index=True, blank=True, null=True)
    venue = models.ForeignKey(
        Hotel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sessions",
        db_index=True,
    )
    location = models.CharField(max_length=200, null=True, blank=True)
    entertainment = models.TextField(
        blank=True, help_text="Describe the entertainment planned"
    )
    unique_string = models.CharField(
        max_length=10,
        null=True,
        blank=True,
    )
    # GenericRelation for custom field values
    custom_field_values = GenericRelation(
        'CustomField.CustomFieldValue',
        content_type_field='content_type',
        object_id_field='object_id',
        related_query_name='session'
    )

    class Meta:
        ordering = ("start_time",)

    def __str__(self):
        return f"{self.title} @ {self.start_time:%H:%M}"


class SessionField(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(
        max_length=50,
        unique=True,
        help_text="Exact field name on Session (e.g. 'title', 'start_time')",
    )
    label = models.CharField(
        max_length=100, help_text="Human-readable label (e.g. 'Session Title')"
    )

    def __str__(self):
        return self.label
