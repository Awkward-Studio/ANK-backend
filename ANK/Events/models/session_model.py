import uuid
from django.db import models
from django.contrib.contenttypes.fields import GenericRelation
from Events.models.event_model import Event
from CustomField.models import CustomFieldValue


class Session(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, related_name="sessions", on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    start_time = models.DateTimeField(db_index=True)
    end_time = models.DateTimeField(db_index=True)
    custom_field_values = GenericRelation(
        CustomFieldValue,
        content_type_field="content_type",
        object_id_field="object_id",
    )

    class Meta:
        ordering = ("start_time",)

    def __str__(self):
        return f"{self.title} @ {self.start_time:%H:%M}"
