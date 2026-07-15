import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
import os
import requests

from django.shortcuts import get_object_or_404

from MessageTemplates.models import WhatsAppBusinessAccount
from MessageTemplates.serializers import WhatsAppBusinessAccountSerializer, WhatsAppPhoneNumberSerializer
from MessageTemplates.services.meta_reconciliation import reconcile_all_wabas

logger = logging.getLogger(__name__)
WEBHOOK_SECRET = os.getenv("DJANGO_RSVP_SECRET", "")

class WABAListCreateView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        token = request.headers.get("X-Webhook-Token", "")
        if not WEBHOOK_SECRET or token != WEBHOOK_SECRET:
            return Response({"error": "Unauthorized"}, status=403)
            
        qs = WhatsAppBusinessAccount.objects.all()
        ser = WhatsAppBusinessAccountSerializer(qs, many=True)
        return Response(ser.data)

    def post(self, request):
        token = request.headers.get("X-Webhook-Token", "")
        if not WEBHOOK_SECRET or token != WEBHOOK_SECRET:
            return Response({"error": "Unauthorized"}, status=403)
            
        waba_id = request.data.get("waba_id")
        name = request.data.get("name")
        access_token = request.data.get("access_token")
        
        if not all([waba_id, name]):
            return Response({"error": "Missing required fields"}, status=400)
        if not access_token:
            return Response({"error": "Access token is required to verify this WABA before saving"}, status=400)

        verify_response = requests.get(
            f"https://graph.facebook.com/v20.0/{waba_id}/phone_numbers",
            params={"access_token": access_token, "limit": 1},
            timeout=10,
        )
        if not verify_response.ok:
            try:
                payload = verify_response.json()
            except ValueError:
                payload = {}
            error = payload.get("error") or {}
            return Response(
                {
                    "error": "Meta could not verify this WABA for the supplied token",
                    "details": error.get("message") or verify_response.text[:300],
                },
                status=400,
            )
            
        waba, created = WhatsAppBusinessAccount.objects.update_or_create(
            waba_id=waba_id,
            defaults={
                "name": name,
                "is_active": True
            }
        )
        if access_token:
            from django.conf import settings
            if not getattr(settings, "WHATSAPP_ENCRYPTION_KEY", None):
                return Response({"error": "WHATSAPP_ENCRYPTION_KEY not configured for token storage"}, status=500)
            waba.set_token(access_token)
        
        waba.save()
        
        ser = WhatsAppBusinessAccountSerializer(waba)
        return Response(ser.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class WABADetailView(APIView):
    permission_classes = [AllowAny]

    def _authorize(self, request):
        token = request.headers.get("X-Webhook-Token", "")
        return WEBHOOK_SECRET and token == WEBHOOK_SECRET

    def delete(self, request, waba_id: str):
        if not self._authorize(request):
            return Response({"error": "Unauthorized"}, status=403)

        waba = get_object_or_404(WhatsAppBusinessAccount, waba_id=waba_id)
        waba.delete()
        return Response({"success": True, "deleted_waba_id": waba_id}, status=status.HTTP_200_OK)


class WABAMetaStatusView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        token = request.headers.get("X-Webhook-Token", "")
        if not WEBHOOK_SECRET or token != WEBHOOK_SECRET:
            return Response({"error": "Unauthorized"}, status=403)

        waba_id = request.query_params.get("waba_id")
        waba_qs = WhatsAppBusinessAccount.objects.prefetch_related("phone_numbers")
        if waba_id:
            waba_qs = waba_qs.filter(waba_id=waba_id)

        results = reconcile_all_wabas(waba_qs)
        payload = []
        for result in results:
            waba = next((item for item in waba_qs if item.waba_id == result["waba_id"]), None)
            if not waba:
                continue

            numbers = result["numbers"]
            meta_details_by_phone_id = result.get("meta_details_by_phone_id", {})
            serialized_numbers = WhatsAppPhoneNumberSerializer(numbers, many=True).data
            for number in serialized_numbers:
                number["meta_details"] = meta_details_by_phone_id.get(
                    str(number["phone_number_id"])
                )
            counts = {
                "active": sum(1 for phone in numbers if phone.meta_status == "active"),
                "blocked": sum(1 for phone in numbers if phone.meta_status == "blocked"),
                "logged_out": sum(1 for phone in numbers if phone.meta_status == "logged_out"),
                "unknown": sum(1 for phone in numbers if phone.meta_status == "unknown"),
            }
            payload.append(
                {
                    "waba": WhatsAppBusinessAccountSerializer(waba).data,
                    "fetch_error": result["fetch_error"],
                    "meta_phone_number_ids": result["meta_phone_number_ids"],
                    "counts": counts,
                    "numbers": serialized_numbers,
                    "template_management": result["template_management"],
                }
            )

        return Response({"success": True, "wabas": payload}, status=status.HTTP_200_OK)
