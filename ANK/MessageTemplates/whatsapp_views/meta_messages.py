from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from MessageTemplates.models import WhatsAppPhoneNumber
from MessageTemplates.permissions import IsAuthenticatedOrInternalService
from MessageTemplates.services.meta_graph import MetaGraphClient, MetaGraphError


class MetaMessageSendView(APIView):
    permission_classes = [IsAuthenticatedOrInternalService]

    def post(self, request):
        phone_number_id = str(request.data.get("phone_number_id") or "")
        payload = request.data.get("payload")
        if not phone_number_id or not isinstance(payload, dict):
            return Response(
                {"error": "phone_number_id and payload are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if payload.get("messaging_product") != "whatsapp" or not payload.get("to"):
            return Response(
                {"error": "Invalid WhatsApp message payload"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if payload.get("type") not in {"text", "template", "image", "video", "audio", "document"}:
            return Response({"error": "Unsupported message type"}, status=status.HTTP_400_BAD_REQUEST)

        phone = get_object_or_404(
            WhatsAppPhoneNumber.objects.select_related("business_account"),
            phone_number_id=phone_number_id,
            is_active=True,
        )
        token = phone.get_access_token()
        try:
            data = MetaGraphClient(token).post(f"{phone_number_id}/messages", json=payload)
        except MetaGraphError as error:
            return Response(
                {
                    "error": {
                        "message": str(error),
                        "code": error.code,
                        "error_subcode": error.subcode,
                        "fbtrace_id": error.fbtrace_id,
                    }
                },
                status=error.status_code if error.status_code and error.status_code < 500 else 502,
            )
        phone.last_used_at = timezone.now()
        phone.save(update_fields=["last_used_at"])
        return Response(data, status=status.HTTP_200_OK)
