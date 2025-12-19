import uuid
from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey


class CustomFieldDefinition(models.Model):
    FIELD_TYPE_CHOICES = [
        ("text", "Text"),
        ("number", "Number"),
        ("date", "Date"),
        ("boolean", "Boolean"),
        # add more as needed...
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(
        max_length=100, help_text="Internal name (e.g. 'speaker_bio')"
    )
    label = models.CharField(
        max_length=200, help_text="Human‐readable label (e.g. 'Speaker Bio')"
    )
    field_type = models.CharField(max_length=20, choices=FIELD_TYPE_CHOICES)
    help_text = models.CharField(
        max_length=300, blank=True, help_text="Optional help text"
    )
    # content_type tells us which model this applies to (Event or Session, etc.)
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        help_text="The model this custom field applies to",
    )
    event = models.ForeignKey(
        'Events.Event',
        on_delete=models.CASCADE,
        related_name='custom_field_definitions',
        help_text="The event this custom field belongs to"
    )

    class Meta:
        unique_together = ('event', 'content_type', 'name')

    def __str__(self):
        event_name = self.event.name if self.event else "No Event"
        return f"{self.label} (for {self.content_type.model} in {event_name})"


class CustomFieldValue(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    definition = models.ForeignKey(
        CustomFieldDefinition, on_delete=models.CASCADE, related_name="values"
    )
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    # Use CharField to support UUID primary keys (all models use UUIDField)
    object_id = models.CharField(max_length=36)
    content_object = GenericForeignKey("content_type", "object_id")
    # store everything as text and cast later if needed
    value = models.TextField()

    class Meta:
        unique_together = ("definition", "content_type", "object_id")

    def __str__(self):
        return f"{self.definition.label}: {self.value}"
