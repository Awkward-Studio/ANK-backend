import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import os
from django.conf import settings as django_settings

from django.shortcuts import get_object_or_404

from MessageTemplates.models import WhatsAppBusinessAccount
from MessageTemplates.serializers import WhatsAppBusinessAccountSerializer, WhatsAppPhoneNumberSerializer
from MessageTemplates.services.meta_reconciliation import reconcile_all_wabas
from MessageTemplates.permissions import IsWhatsAppAdminOrInternalService

logger = logging.getLogger(__name__)
class WABAListCreateView(APIView):
    permission_classes = [IsWhatsAppAdminOrInternalService]

    def get(self, request):
        qs = WhatsAppBusinessAccount.objects.all()
        ser = WhatsAppBusinessAccountSerializer(qs, many=True)
        return Response(ser.data)

    def post(self, request):
        waba_id = request.data.get("waba_id")
        name = request.data.get("name")
        access_token = request.data.get("access_token")
        
        if not all([waba_id, name]):
            return Response({"error": "Missing required fields"}, status=400)
            
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


class WhatsAppAdminCheckView(APIView):
    permission_classes = [IsWhatsAppAdminOrInternalService]

    def get(self, request):
        return Response({"authorized": True}, status=status.HTTP_200_OK)


class WABADetailView(APIView):
    permission_classes = [IsWhatsAppAdminOrInternalService]

    def delete(self, request, waba_id: str):
        waba = get_object_or_404(WhatsAppBusinessAccount, waba_id=waba_id)
        waba.delete()
        return Response({"success": True, "deleted_waba_id": waba_id}, status=status.HTTP_200_OK)


class WABAMetaStatusView(APIView):
    permission_classes = [IsWhatsAppAdminOrInternalService]

    def get(self, request):
        """Return saved snapshots without making a Meta request."""
        waba_id = request.query_params.get("waba_id")
        waba_qs = WhatsAppBusinessAccount.objects.prefetch_related("phone_numbers")
        if waba_id:
            waba_qs = waba_qs.filter(waba_id=waba_id)

        results = [
            {
                "waba_id": waba.waba_id,
                "fetch_error": waba.meta_fetch_error_message,
                "numbers": list(waba.phone_numbers.all()),
                "meta_phone_number_ids": [
                    phone.phone_number_id
                    for phone in waba.phone_numbers.all()
                    if phone.meta_seen_in_waba
                ],
                "meta_details_by_phone_id": {
                    phone.phone_number_id: phone.meta_details_snapshot
                    for phone in waba.phone_numbers.all()
                },
                "template_management": {
                    "status": waba.template_access_status,
                    "reason": waba.template_access_reason,
                    "last_checked_at": waba.template_access_last_checked_at,
                },
            }
            for waba in waba_qs
        ]
        return self._response(waba_qs, results)

    def post(self, request):
        """Refresh saved snapshots from Meta, isolated by WABA."""
        waba_id = request.data.get("waba_id") or request.query_params.get("waba_id")
        waba_qs = WhatsAppBusinessAccount.objects.prefetch_related("phone_numbers")
        if waba_id:
            waba_qs = waba_qs.filter(waba_id=waba_id)

        results = reconcile_all_wabas(waba_qs)
        return self._response(waba_qs, results)

    @staticmethod
    def _response(waba_qs, results):
        wabas_by_id = {waba.waba_id: waba for waba in waba_qs}
        payload = []
        for result in results:
            waba = wabas_by_id.get(result["waba_id"])
            if not waba:
                continue

            numbers = result["numbers"]
            meta_details_by_phone_id = result.get("meta_details_by_phone_id", {})
            serialized_numbers = WhatsAppPhoneNumberSerializer(numbers, many=True).data
            for number in serialized_numbers:
                number["meta_details"] = meta_details_by_phone_id.get(
                    str(number["phone_number_id"])
                )
            counts = {}
            for phone in numbers:
                counts[phone.meta_access_state] = counts.get(phone.meta_access_state, 0) + 1
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

        return Response(
            {
                "success": True,
                "graph_api_version": django_settings.META_GRAPH_API_VERSION,
                "wabas": payload,
            },
            status=status.HTTP_200_OK,
        )
