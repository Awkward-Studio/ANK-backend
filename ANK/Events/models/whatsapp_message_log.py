import uuid

from django.db import models
from django.utils import timezone


class WhatsAppMessageLog(models.Model):
    """
    Track WhatsApp message delivery status.

    This model stores status updates received from Meta's webhook
    for tracking message delivery (sent → delivered → read / failed).
    """

    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("sending", "Sending"),
        ("sent", "Sent"),
        ("delivered", "Delivered"),
        ("read", "Read"),
        ("failed", "Failed"),
    )

    MESSAGE_TYPE_CHOICES = (
        ("rsvp", "RSVP"),
        ("custom", "Custom"),
        ("travel", "Travel"),
        ("template", "Template"),
        ("bulk", "Bulk"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Message identifiers
    wamid = models.CharField(max_length=255, unique=True, db_index=True)
    recipient_id = models.CharField(
        max_length=50, db_index=True
    )  # Phone number (digits only)
    
    # Multi-number support: Track which of OUR numbers sent/received this message
    sender_phone_number_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        db_index=True,
        help_text="Phone Number ID of the sender (which of OUR numbers sent/received this)"
    )

    # Status tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="sent")

    # Message type
    message_type = models.CharField(
        max_length=20, choices=MESSAGE_TYPE_CHOICES, default="rsvp"
    )

    # Direction (new)
    DIRECTION_CHOICES = (
        ("inbound", "Inbound"),
        ("outbound", "Outbound"),
    )
    direction = models.CharField(
        max_length=10, choices=DIRECTION_CHOICES, default="outbound"
    )

    # Content (new)
    body = models.TextField(null=True, blank=True)
    
    # Media details
    media_url = models.TextField(null=True, blank=True)
    media_type = models.CharField(max_length=20, null=True, blank=True)  # e.g. image, video, document
    media_id = models.CharField(max_length=255, null=True, blank=True)

    # Timestamps
    sent_at = models.DateTimeField(default=timezone.now)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)

    # Error details (if failed)
    error_code = models.CharField(max_length=50, null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)

    # Relationships
    event_registration_id = models.CharField(
        max_length=255, null=True, blank=True, db_index=True
    )
    event_id = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    guest_id = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    guest_name = models.CharField(max_length=255, null=True, blank=True)

    # Template info
    template_name = models.CharField(max_length=255, null=True, blank=True)

    # Flow type for categorization (legacy, use message_type instead)
    flow_type = models.CharField(max_length=32, null=True, blank=True)

    # Multi-number support: Track which of OUR numbers sent/received this message
    sender_phone_number_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        db_index=True,
        help_text="Phone Number ID of the sender (which of OUR numbers sent/received this)",
    )

    # Campaign Link
    campaign = models.ForeignKey(
        "MessageTemplates.BroadcastCampaign",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="logs",
        db_index=True,
        help_text="The campaign this message belongs to, if any."
    )

    class Meta:
        ordering = ["-sent_at"]
        indexes = [
            models.Index(fields=["recipient_id", "-sent_at"]),
            models.Index(fields=["status"]),
            models.Index(fields=["-sent_at"]),
            models.Index(fields=["event_registration_id", "-sent_at"]),
            models.Index(fields=["event_id", "-sent_at"]),
            models.Index(fields=["guest_id", "-sent_at"]),
            models.Index(fields=["sender_phone_number_id", "-sent_at"]),
            models.Index(fields=["recipient_id", "sender_phone_number_id", "-sent_at"]),
        ]

    def __str__(self):
        return f"{self.recipient_id} - {self.status} ({self.wamid[:30]}...)"
