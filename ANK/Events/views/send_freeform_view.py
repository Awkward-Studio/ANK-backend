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
    message = serializers.CharField(max_length=4096, required=False, allow_blank=True)
    media_url = serializers.CharField(required=False, allow_blank=True)
    media_type = serializers.CharField(required=False, allow_blank=True)  # image, video
    caption = serializers.CharField(required=False, allow_blank=True)


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
            wa_message_id = ""
            media_url = serializer.validated_data.get("media_url")
            media_type = serializer.validated_data.get("media_type")
            caption = serializer.validated_data.get("caption")

            if media_url and media_type:
                # Send Media
                wa_message_id = MessageLogger.send_media_message(
                    reg, media_type, media_url, caption=message or caption
                )
            else:
                # Send Text
                if not message:
                     return Response(
                        {"ok": False, "status": "failed", "error": "Message text is required if no media attached"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                wa_message_id = send_freeform_text(phone, message)
                # Log usage
                MessageLogger.log_outbound(
                    event_registration=reg,
                    content=message,
                    wa_message_id=wa_message_id,
                    message_type="content",
                )

            # Pause any active travel session so user replies aren't treated as travel answers
            try:
                from Logistics.models.travel_detail_capture_session import TravelCaptureSession
                session = TravelCaptureSession.objects.filter(registration=reg).first()
                if session and not session.is_complete and session.step:
                    logger.info(f"[FREEFORM] Pausing travel session for reg {reg.id} (was at step {session.step})")
                    session.step = ""  # Clear step to pause the flow
                    session.save(update_fields=["step"])
            except Exception as pause_exc:
                logger.warning(f"[FREEFORM] Failed to pause session: {pause_exc}")

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
