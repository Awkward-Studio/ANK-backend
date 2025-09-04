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
    Stores a message we wanted to send to a guest but couldn't
    because the 24h WhatsApp session was closed.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Link to event + guest
    event = models.ForeignKey(
        Event, on_delete=models.CASCADE, related_name="queued_messages"
    )
    registration = models.ForeignKey(
        EventRegistration, on_delete=models.CASCADE, related_name="queued_messages"
    )

    # The template that generated this message (optional)
    template = models.ForeignKey(
        MessageTemplate, on_delete=models.SET_NULL, null=True, blank=True
    )

    # Fully rendered text we planned to send
    rendered_text = models.TextField()

    # Status tracking
    sent = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    sent_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"QueuedMessage(reg={self.registration_id}, sent={self.sent})"
