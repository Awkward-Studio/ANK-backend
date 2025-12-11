import uuid
from django.db import models
from django.utils import timezone
from Events.models.event_registration_model import EventRegistration
from Events.models.event_model import Event


class MessageTemplate(models.Model):
    """
    A message template scoped (optionally) to an Event.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="message_templates",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=200, db_index=True)
    message = models.TextField()
    desc = models.TextField(blank=True, null=True)
    is_rsvp_message = models.BooleanField(default=False)

    # Media attachment fields for template messages
    MEDIA_TYPE_CHOICES = [
        ('image', 'Image'),
        ('video', 'Video'),
        ('document', 'Document'),
    ]
    media_type = models.CharField(
        max_length=20,
        choices=MEDIA_TYPE_CHOICES,
        null=True,
        blank=True,
        help_text='Type of media attached to this template'
    )
    media_url = models.URLField(
        max_length=500,
        null=True,
        blank=True,
        help_text='Original media file URL'
    )
    media_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text='WhatsApp Business API media ID returned after upload'
    )

    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = (("event", "name"),)
        ordering = ("name",)

    def __str__(self):
        return f"{self.name} ({'RSVP' if self.is_rsvp_message else 'General'})"


class MessageTemplateVariable(models.Model):
    """
    A variable belonging to a MessageTemplate, with an optional default value and ordering.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    template = models.ForeignKey(
        MessageTemplate, on_delete=models.CASCADE, related_name="variables"
    )
    variable_name = models.CharField(max_length=100)
    variable_value = models.TextField(blank=True)  # optional default/fallback
    variable_description = models.TextField(blank=True)
    variable_position = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = (("template", "variable_name"),)
        ordering = ("variable_position", "variable_name")

    def __str__(self):
        return f"{self.variable_name} (template={self.template_id})"


class QueuedMessage(models.Model):
    """
    Stores the final rendered local message we wanted to send but couldn't
    because the 24h WhatsApp window was closed.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    event = models.ForeignKey(
        Event, on_delete=models.CASCADE, related_name="queued_messages"
    )
    registration = models.ForeignKey(
        EventRegistration, on_delete=models.CASCADE, related_name="queued_messages"
    )

    template = models.ForeignKey(
        MessageTemplate, on_delete=models.SET_NULL, null=True, blank=True
    )

    # Final text already rendered with {{vars}}. No surprises later.
    rendered_text = models.TextField()

    sent = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["registration", "sent"]),
        ]

    def mark_sent(self):
        self.sent = True
        self.sent_at = timezone.now()
        self.save(update_fields=["sent", "sent_at"])

    def __str__(self):
        return f"QueuedMessage(reg={self.registration_id}, sent={self.sent})"
