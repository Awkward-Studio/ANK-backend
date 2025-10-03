"""
Tracks the step-by-step Travel Details capture over WhatsApp for a single EventRegistration.
One active session per registration. Resumes from where the guest left off.
"""

import uuid
from django.db import models
from django.utils import timezone
from Events.models.event_registration_model import EventRegistration


class TravelCaptureSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    registration = models.OneToOneField(
        EventRegistration, on_delete=models.CASCADE, related_name="travel_capture"
    )
    state = models.JSONField(default=dict)
    step = models.CharField(max_length=64, default="opt_in")
    last_prompt_step = models.CharField(max_length=64, blank=True, default="")
    is_complete = models.BooleanField(default=False)
    last_msg_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"TravelCaptureSession(reg={self.registration_id}, step={self.step}, done={self.is_complete})"
