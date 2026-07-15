import requests
import os
import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from django.shortcuts import get_object_or_404

from MessageTemplates.models import WhatsAppPhoneNumber, WhatsAppBusinessAccount
from MessageTemplates.serializers import (
    WhatsAppPhoneNumberSerializer,
    WhatsAppPhoneNumberWriteSerializer,
)
from MessageTemplates.services.meta_reconciliation import reconcile_all_wabas

logger = logging.getLogger(__name__)
WEBHOOK_SECRET = os.getenv("DJANGO_RSVP_SECRET", "")


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

    permission_classes = [AllowAny]  # Verify with X-Webhook-Token header

    def post(self, request):
        # Verify webhook token
        token = request.headers.get("X-Webhook-Token", "")
        if not WEBHOOK_SECRET or token != WEBHOOK_SECRET:
            logger.warning("[STORE_PHONE] Invalid or missing webhook token")
            return Response(
                {"success": False, "error": "Invalid authentication token"},
                status=status.HTTP_403_FORBIDDEN,
            )
        
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
                sub_url = f"https://graph.facebook.com/v20.0/{waba_id}/subscribed_apps"
                try:
                    sub_res = requests.post(
                        sub_url, 
                        params={"access_token": access_token},
                        timeout=10
                    )
                    if sub_res.ok:
                        logger.info(f"[STORE_PHONE] Successfully subscribed webhooks for WABA {waba_id}")
                    else:
                        logger.warning(f"[STORE_PHONE] Webhook subscription failed for {waba_id}: {sub_res.text}")
                except Exception as sub_err:
                    logger.error(f"[STORE_PHONE] Error calling Meta Graph API for subscription: {sub_err}")
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

        except ValidationError as e:
            logger.warning(f"[STORE_PHONE] Meta validation failed: {e.detail}")
            return Response(
                {"success": False, "errors": e.detail},
                status=status.HTTP_400_BAD_REQUEST,
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

    permission_classes = [AllowAny]  # Verify with X-Webhook-Token header

    def get(self, request):
        # Verify webhook token
        token = request.headers.get("X-Webhook-Token", "")
        if not WEBHOOK_SECRET or token != WEBHOOK_SECRET:
            logger.warning("[LIST_PHONES] Invalid or missing webhook token")
            return Response(
                {"success": False, "error": "Invalid authentication token"},
                status=status.HTTP_403_FORBIDDEN,
            )
        
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

    permission_classes = [AllowAny]  # Verify with X-Webhook-Token header

    def get(self, request, phone_number_id: str):
        """Get details of a specific phone number"""
        # Verify webhook token
        token = request.headers.get("X-Webhook-Token", "")
        if not WEBHOOK_SECRET or token != WEBHOOK_SECRET:
            logger.warning(f"[PHONE_DETAIL] Invalid or missing webhook token")
            return Response(
                {"success": False, "error": "Invalid authentication token"},
                status=status.HTTP_403_FORBIDDEN,
            )
        
        logger.info(f"[PHONE_DETAIL] Fetching phone_number_id={phone_number_id}")

        phone = get_object_or_404(WhatsAppPhoneNumber, phone_number_id=phone_number_id)
        serializer = WhatsAppPhoneNumberSerializer(phone)

        return Response(
            {"success": True, "phone_number": serializer.data},
            status=status.HTTP_200_OK,
        )

    def patch(self, request, phone_number_id: str):
        """Update phone number settings (is_active, is_default, etc.)"""
        # Verify webhook token
        token = request.headers.get("X-Webhook-Token", "")
        if not WEBHOOK_SECRET or token != WEBHOOK_SECRET:
            logger.warning(f"[PHONE_UPDATE] Invalid or missing webhook token")
            return Response(
                {"success": False, "error": "Invalid authentication token"},
                status=status.HTTP_403_FORBIDDEN,
            )
        
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
    permission_classes = [AllowAny]

    def get(self, request):
        token = request.headers.get("X-Webhook-Token", request.query_params.get("token", ""))
        if not WEBHOOK_SECRET or token != WEBHOOK_SECRET:
            logger.warning("[META_STATUS] Invalid or missing webhook token")
            return Response(
                {"success": False, "error": "Invalid authentication token"},
                status=status.HTTP_403_FORBIDDEN,
            )

        logger.info("[META_STATUS] Generating Meta Graph API report for all active numbers")

        checked_wabas = set()
        phone_numbers = WhatsAppPhoneNumber.objects.filter(is_active=True)
        report = []

        for phone in phone_numbers:
            waba_id = phone.waba_id
            access_token = phone.get_access_token()
            
            if not waba_id or not access_token:
                report.append({
                    "display_number": phone.display_phone_number,
                    "name": phone.verified_name,
                    "status": "ERROR",
                    "message": "Missing WABA ID or Access Token in database"
                })
                continue
                
            if waba_id in checked_wabas:
                continue
                
            checked_wabas.add(waba_id)
            url = f"https://graph.facebook.com/v20.0/{waba_id}/phone_numbers"
            try:
                res = requests.get(url, params={"access_token": access_token}, timeout=10)
                data = res.json()
                
                if res.ok:
                    meta_numbers = data.get("data", [])
                    if not meta_numbers:
                        report.append({
                            "waba_id": waba_id,
                            "status": "ERROR",
                            "message": "No phone numbers found in this WABA on Meta's side"
                        })
                    else:
                        for n in meta_numbers:
                            report.append({
                                "waba_id": waba_id,
                                "meta_id": n.get('id'),
                                "display_number": n.get('display_phone_number'),
                                "name": n.get('verified_name'),
                                "status": n.get('status'),
                                "quality": n.get('quality_rating')
                            })
                else:
                    report.append({
                        "waba_id": waba_id,
                        "status": "META_API_ERROR",
                        "message": data.get('error', {}).get('message', 'Unknown Error'),
                        "error_details": data
                    })
            except Exception as e:
                report.append({
                    "waba_id": waba_id,
                    "status": "REQUEST_FAILED",
                    "message": str(e)
                })

        return Response({
            "success": True,
            "report": report
        }, status=status.HTTP_200_OK)
