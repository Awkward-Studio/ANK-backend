import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, serializers
from django.shortcuts import get_object_or_404

from Events.models.event_registration_model import EventRegistration
from Events.services.message_logger import MessageLogger
from MessageTemplates.services.whatsapp import send_freeform_text, within_24h_window

logger = logging.getLogger(__name__)


class SendFreeformInput(serializers.Serializer):
    message = serializers.CharField(max_length=4096, required=True)


class SendFreeformMessageView(APIView):
    """
    POST /api/events/{event_id}/registrations/{registration_id}/send-freeform/
    Sends a freeform text message to a guest via WhatsApp.
    Only works within the 24-hour service window.
    """

    def post(self, request, event_id: str, registration_id: str):
        serializer = SendFreeformInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        message = serializer.validated_data["message"]

        # Fetch registration
        reg = get_object_or_404(
            EventRegistration.objects.select_related("guest", "event"),
            id=registration_id,
            event_id=event_id,
        )

        # Check service window using responded_on
        if not within_24h_window(reg.responded_on):
            return Response(
                {
                    "ok": False,
                    "status": "failed",
                    "error": "Service window expired. Last inbound message was more than 24 hours ago.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get guest phone
        phone = getattr(reg.guest, "phone", None)
        if not phone:
            return Response(
                {"ok": False, "status": "failed", "error": "Guest has no phone number"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Send via existing WhatsApp service
        try:
            wa_message_id = send_freeform_text(phone, message)

            # Log outbound message
            MessageLogger.log_outbound(
                event_registration=reg,
                content=message,
                wa_message_id=wa_message_id,
                message_type="content",
            )

            return Response(
                {"ok": True, "status": "sent", "message_id": wa_message_id},
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            logger.exception(f"Failed to send freeform message for reg {reg.id}")
            return Response(
                {"ok": False, "status": "failed", "error": f"WhatsApp API error: {e}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )
