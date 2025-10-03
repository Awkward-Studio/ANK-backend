import os
import logging
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, serializers
from rest_framework.permissions import AllowAny

from Events.models.event_registration_model import EventRegistration
from MessageTemplates.models import QueuedMessage
from MessageTemplates.services.whatsapp import (
    _norm_digits,
    send_freeform_text,
)

logger = logging.getLogger(__name__)
SHARED = os.getenv("DJANGO_RSVP_SECRET", "")


class FlushInput(serializers.Serializer):
    registration_id = serializers.UUIDField()


class FlushQueuedMessagesView(APIView):
    """
    POST /api/message-templates/flush-after-resume/
    Headers: X-Webhook-Token: <DJANGO_RSVP_SECRET>
    Body: { "registration_id": "<uuid>" }

    Sends all unsent queued messages for the registration, then marks them sent.
    """

    permission_classes = [AllowAny]  # We verify with the shared header instead

    def post(self, request):
        # Verify shared secret
        token = request.headers.get("X-Webhook-Token", "")
        if not SHARED or token != SHARED:
            return Response(
                {"ok": False, "error": "invalid token"},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = FlushInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        reg_id = serializer.validated_data["registration_id"]

        reg = get_object_or_404(
            EventRegistration.objects.select_related("guest"), id=reg_id
        )
        to_wa = _norm_digits(getattr(reg.guest, "phone", None))
        if not to_wa:
            return Response(
                {"ok": False, "error": "guest_has_no_phone"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        qs = QueuedMessage.objects.filter(registration=reg, sent=False).order_by(
            "created_at"
        )
        sent = 0
        errors = []

        for qm in qs:
            try:
                send_freeform_text(to_wa, qm.rendered_text)
                qm.mark_sent()
                sent += 1
            except Exception as e:
                # Keep in queue for retries
                logger.exception("Failed to flush queued message %s", qm.id)
                errors.append({"id": str(qm.id), "error": str(e)})

        # Update last responded timestamp so subsequent messages are in-window
        reg.responded_on = timezone.now()
        reg.save(update_fields=["responded_on"])

        return Response(
            {"ok": True, "sent": sent, "errors": errors}, status=status.HTTP_200_OK
        )
