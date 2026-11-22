import uuid
from django.conf import settings
from django.db import models
from django.contrib.contenttypes.fields import GenericRelation
from Guest.models import Guest
from Events.models.session_model import Session


class SessionRegistration(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    guest = models.ForeignKey(Guest, on_delete=models.CASCADE)
    session = models.ForeignKey(
        Session, on_delete=models.CASCADE, related_name="registrations"
    )
    registered_on = models.DateTimeField(auto_now_add=True)
    is_checked_in = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether the guest has entered/checked-in to this function/session",
    )
    checked_in_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Timestamp when the guest checked into this function",
    )
    checked_in_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="session_checkins",
        help_text="Staff or security user who checked the guest into this function",
    )

    # GenericRelation for custom field values
    custom_field_values = GenericRelation(
        'CustomField.CustomFieldValue',
        content_type_field='content_type',
        object_id_field='object_id',
        related_query_name='sessionregistration'
    )

    class Meta:
        unique_together = ("guest", "session")
        # ↑ prevents a guest signing up for the same Session twice

    def __str__(self):
        return f"{self.guest} in {self.session}"
