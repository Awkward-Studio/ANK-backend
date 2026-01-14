import uuid
from django.db import models
from Events.models.event_registration_model import EventRegistration

class ConversationMessage(models.Model):
    DIRECTION_CHOICES = (
        ('inbound', 'Inbound'),
        ('outbound', 'Outbound'),
    )
    
    STATUS_CHOICES = (
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('read', 'Read'),
        ('failed', 'Failed'),
        ('received', 'Received'), # For inbound
    )

    MESSAGE_TYPE_CHOICES = (
        ('content', 'Content'),
        ('template', 'Template'),
        ('rsvp', 'RSVP'),
        ('travel', 'Travel'),
        ('system', 'System'),
        ('button', 'Button'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_registration = models.ForeignKey(
        EventRegistration, 
        on_delete=models.CASCADE, 
        related_name='conversation_messages'
    )
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES)
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPE_CHOICES, default='content')
    content = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='sent')
    
    # WhatsApp specific - NOT unique since we may not always have actual message IDs
    wa_message_id = models.CharField(max_length=100, blank=True, null=True)
    template_name = models.CharField(max_length=100, blank=True, null=True)

    # Multi-number support: Track which of OUR numbers sent/received this
    sender_phone_number_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        db_index=True,
        help_text="Phone Number ID that sent/received this message (for multi-number support)"
    )

    # Media details
    media_url = models.TextField(null=True, blank=True)
    media_type = models.CharField(max_length=20, null=True, blank=True)  # e.g. image, video
    media_id = models.CharField(max_length=255, null=True, blank=True)
    
    # Generic metadata
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['event_registration', '-timestamp']),
            models.Index(fields=['wa_message_id']),
        ]

    def __str__(self):
        return f"{self.direction} - {self.event_registration.guest.name} - {self.timestamp}"
