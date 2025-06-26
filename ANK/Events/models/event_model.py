import uuid
from django.db import models
from django.contrib.contenttypes.fields import GenericRelation
from CustomField.models import CustomFieldValue


class Event(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    location = models.CharField(max_length=200)
    venue = models.CharField(max_length=200)
    start_date = models.DateField(db_index=True)
    end_date = models.DateField(db_index=True)
    # allow querying event.custom_field_values
    custom_field_values = GenericRelation(
        CustomFieldValue,
        content_type_field="content_type",
        object_id_field="object_id",
    )

    def __str__(self):
        return f"{self.name} ({self.start_date:%Y-%m-%d}–{self.end_date:%Y-%m-%d})"
