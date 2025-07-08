import uuid
from django.db import models
from django.contrib.contenttypes.fields import GenericRelation
from Events.models.event_model import Event
from CustomField.models import CustomFieldValue


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
    venue = models.CharField(max_length=200, blank=True, null=True)
    location = models.CharField(max_length=200, null=True, blank=True)
    entertainment = models.TextField(
        blank=True, help_text="Describe the entertainment planned"
    )
    # allow querying session.custom_field_values
    custom_field_values = GenericRelation(
        CustomFieldValue,
        content_type_field="content_type",
        object_id_field="object_id",
    )

    class Meta:
        ordering = ("start_time",)

    def __str__(self):
        return f"{self.title} @ {self.start_time:%H:%M}"
