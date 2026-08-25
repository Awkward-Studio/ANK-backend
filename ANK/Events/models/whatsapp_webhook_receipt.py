import uuid

from django.db import models


class WhatsAppWebhookReceipt(models.Model):
    """Database-backed idempotency receipt for Meta webhook events."""

    STATE_CHOICES = (
        ("processing", "Processing"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_key = models.CharField(max_length=512, unique=True, db_index=True)
    wamid = models.CharField(max_length=255, blank=True, default="", db_index=True)
    event_kind = models.CharField(max_length=32, blank=True, default="")
    event_name = models.CharField(max_length=64, blank=True, default="")
    source_app = models.CharField(max_length=64, blank=True, default="")
    state = models.CharField(max_length=16, choices=STATE_CHOICES, default="processing")
    claim_token = models.UUIDField(null=True, blank=True)
    lease_expires_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveIntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)
    first_seen_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-last_seen_at"]

