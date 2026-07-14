import requests
import os
import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404

from MessageTemplates.models import WhatsAppPhoneNumber, WhatsAppBusinessAccount
from MessageTemplates.serializers import (
    WhatsAppPhoneNumberSerializer,
    WhatsAppPhoneNumberWriteSerializer,
)
from MessageTemplates.services.meta_reconciliation import reconcile_all_wabas
from MessageTemplates.permissions import (
    IsAuthenticatedOrInternalService,
    IsWhatsAppAdminOrInternalService,
)
from MessageTemplates.services.meta_graph import MetaGraphClient, MetaGraphError

logger = logging.getLogger(__name__)

class StorePhoneNumberView(APIView):
    """
    POST /api/whatsapp/phone-numbers/store/
    Headers: X-Webhook-Token: <DJANGO_RSVP_SECRET>
    
    Store WhatsApp phone number credentials after embedded signup.
    Body: {
        "phone_number_id": "2485856308207334",
        "asset_id": "590466851521920",
        "waba_id": "864800316406577",
        "access_token": "EAAxxxxx...",
        "display_phone_number": "+919876543210",
        "verified_name": "ANK Wedding Services",
        "quality_rating": "GREEN",
        "messaging_limit_tier": "TIER_1K",
        "is_default": false
    }
    """

    permission_classes = [IsWhatsAppAdminOrInternalService]

    def post(self, request):
        logger.info("[STORE_PHONE] Received request to store phone number")
        
        serializer = WhatsAppPhoneNumberWriteSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning(f"[STORE_PHONE] Validation failed: {serializer.errors}")
            return Response(
                {"success": False, "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            phone_number = serializer.save()
            logger.info(
                f"[STORE_PHONE] Successfully stored phone_number_id={phone_number.phone_number_id}"
            )

            # --- NEW: Subscribe the App to this WABA for Webhooks ---
            waba_id = phone_number.waba_id
            access_token = phone_number.get_access_token()
            
            if waba_id and access_token:
                try:
                    MetaGraphClient(access_token).subscribe_waba(waba_id)
                    logger.info("[STORE_PHONE] Subscribed WABA %s", waba_id)
                except MetaGraphError as sub_err:
                    logger.warning("[STORE_PHONE] WABA subscription failed: %s", sub_err)
            # ------------------------------------------------------

            # Return created phone number details
            response_serializer = WhatsAppPhoneNumberSerializer(phone_number)
            return Response(
                {
                    "success": True,
                    "created": True,
                    "phone_number": response_serializer.data,
                },
                status=status.HTTP_201_CREATED,
            )

        except Exception as e:
            logger.exception(f"[STORE_PHONE] Failed to store phone number: {e}")
            return Response(
                {"success": False, "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ListPhoneNumbersView(APIView):
    """
    GET /api/whatsapp/phone-numbers/
    Headers: X-Webhook-Token: <DJANGO_RSVP_SECRET>
    
    Query params:
      - is_active (bool, default: true; pass all to include every status)
      - waba_id (str, optional)
      - sync_meta (bool, default: false)
    
    Returns list of available phone numbers.
    """

    permission_classes = [IsAuthenticatedOrInternalService]

    def get(self, request):
        logger.info("[LIST_PHONES] Fetching phone numbers")

        # Parse query params
        is_active_param = request.query_params.get("is_active", "true").lower()
        waba_id = request.query_params.get("waba_id", None)
        sync_meta = request.query_params.get("sync_meta", "false").lower() == "true"

        if sync_meta:
            waba_qs = WhatsAppBusinessAccount.objects.prefetch_related("phone_numbers")
            if waba_id:
                waba_qs = waba_qs.filter(waba_id=waba_id)
            reconcile_all_wabas(waba_qs)

        # Build query
        queryset = WhatsAppPhoneNumber.objects.all()
        if is_active_param == "true":
            queryset = queryset.filter(is_active=True)
            if sync_meta:
                queryset = queryset.filter(meta_status="active")
        elif is_active_param == "false":
            queryset = queryset.filter(is_active=False)
        if waba_id:
            queryset = queryset.filter(waba_id=waba_id)

        # Order by default first, then last used
        queryset = queryset.order_by("-is_default", "-last_used_at", "-created_at")

        phone_numbers = list(queryset)
        serializer = WhatsAppPhoneNumberSerializer(phone_numbers, many=True)

        logger.info(f"[LIST_PHONES] Returning {len(phone_numbers)} phone numbers")
        return Response(
            {"success": True, "phone_numbers": serializer.data, "count": len(phone_numbers)},
            status=status.HTTP_200_OK,
        )


class PhoneNumberDetailView(APIView):
    """
    GET /api/whatsapp/phone-numbers/<phone_number_id>/
    PATCH /api/whatsapp/phone-numbers/<phone_number_id>/
    Headers: X-Webhook-Token: <DJANGO_RSVP_SECRET>
    
    Get or update a specific phone number.
    """

    permission_classes = [IsWhatsAppAdminOrInternalService]

    def get(self, request, phone_number_id: str):
        """Get details of a specific phone number"""
        logger.info(f"[PHONE_DETAIL] Fetching phone_number_id={phone_number_id}")

        phone = get_object_or_404(WhatsAppPhoneNumber, phone_number_id=phone_number_id)
        serializer = WhatsAppPhoneNumberSerializer(phone)

        return Response(
            {"success": True, "phone_number": serializer.data},
            status=status.HTTP_200_OK,
        )

    def patch(self, request, phone_number_id: str):
        """Update phone number settings (is_active, is_default, etc.)"""
        logger.info(f"[PHONE_UPDATE] Updating phone_number_id={phone_number_id}")

        phone = get_object_or_404(WhatsAppPhoneNumber, phone_number_id=phone_number_id)

        # Allow updating specific fields
        allowed_fields = ["is_active", "is_default", "quality_rating", "messaging_limit_tier"]
        updated_fields = []

        for field in allowed_fields:
            if field in request.data:
                setattr(phone, field, request.data[field])
                updated_fields.append(field)

        if updated_fields:
            phone.save(update_fields=updated_fields)
            logger.info(
                f"[PHONE_UPDATE] Updated fields {updated_fields} for phone_number_id={phone_number_id}"
            )
        else:
            logger.warning(f"[PHONE_UPDATE] No valid fields to update")

        serializer = WhatsAppPhoneNumberSerializer(phone)
        return Response(
            {
                "success": True,
                "message": "Phone number updated",
                "phone_number": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class MetaStatusReportView(APIView):
    """
    GET /api/whatsapp/phone-numbers/meta-status/
    Headers: X-Webhook-Token: <DJANGO_RSVP_SECRET>
    
    Queries the Meta Graph API directly using stored tokens to check 
    the actual validity and restrictions of all active phone numbers.
    """
    permission_classes = [IsWhatsAppAdminOrInternalService]

    def get(self, request):
        logger.info("[META_STATUS] Refreshing report through the central Graph client")
        results = reconcile_all_wabas(
            WhatsAppBusinessAccount.objects.prefetch_related("phone_numbers")
        )
        report = []
        for result in results:
            for phone in result["numbers"]:
                report.append(
                    {
                        "waba_id": phone.waba_id,
                        "meta_id": phone.phone_number_id,
                        "display_number": phone.display_phone_number,
                        "name": phone.verified_name,
                        "access_state": phone.meta_access_state,
                        "seen_in_waba": phone.meta_seen_in_waba,
                        "quality": phone.quality_rating,
                        "code_verification_status": phone.code_verification_status or None,
                        "name_status": phone.name_status or None,
                        "message": phone.meta_fetch_error_message,
                    }
                )
        return Response({"success": True, "report": report})
