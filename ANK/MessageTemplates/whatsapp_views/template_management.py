import logging
import os

import requests
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from MessageTemplates.models import WhatsAppBusinessAccount, WhatsAppPhoneNumber

logger = logging.getLogger(__name__)
WEBHOOK_SECRET = os.getenv("DJANGO_RSVP_SECRET", "")
GRAPH_API_VERSION = os.getenv("META_GRAPH_API_VERSION", "v25.0")
GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"


def _meta_error(response: requests.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text[:300]
    error = payload.get("error") or {}
    return error.get("error_user_msg") or error.get("message") or response.text[:300]


class WhatsAppTemplateManagementView(APIView):
    permission_classes = [AllowAny]

    def _authorize(self, request) -> bool:
        token = request.headers.get("X-Webhook-Token", "")
        return bool(WEBHOOK_SECRET and token == WEBHOOK_SECRET)

    def _resolve_account(self, request, body=None):
        phone_number_id = (body or {}).get("phone_number_id") or request.query_params.get("phone_number_id")
        waba_id = (body or {}).get("waba_id") or request.query_params.get("waba_id")

        if phone_number_id:
            phone = WhatsAppPhoneNumber.objects.select_related("business_account").filter(
                phone_number_id=phone_number_id,
                is_active=True,
            ).first()
            if not phone:
                return None, Response(
                    {"success": False, "error": "Selected WhatsApp phone number is not registered or active in ANK."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            waba = phone.business_account
            if not waba or not waba.is_active:
                return None, Response(
                    {"success": False, "error": "Selected WhatsApp phone number is not linked to an active WABA."},
                    status=status.HTTP_409_CONFLICT,
                )
        elif waba_id:
            waba = WhatsAppBusinessAccount.objects.prefetch_related("phone_numbers").filter(
                waba_id=waba_id,
                is_active=True,
            ).first()
            if not waba:
                return None, Response(
                    {"success": False, "error": "Selected WABA is not registered or active in ANK."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            phone = waba.phone_numbers.filter(is_active=True).first()
        else:
            return None, Response(
                {"success": False, "error": "phone_number_id or waba_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        token = waba.get_token()
        if not token and phone:
            token = phone.get_access_token(allow_env_fallback=False)
        if not token:
            token = os.getenv("WABA_ACCESS_TOKEN", "")
        if not token:
            return None, Response(
                {"success": False, "error": "No stored or configured system-user token is available for this WABA."},
                status=status.HTTP_409_CONFLICT,
            )

        return {"waba": waba, "phone": phone, "token": token}, None

    def get(self, request):
        if not self._authorize(request):
            return Response({"success": False, "error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)

        resolved, error = self._resolve_account(request)
        if error:
            return error

        waba = resolved["waba"]
        response = requests.get(
            f"{GRAPH_API_BASE}/{waba.waba_id}/message_templates",
            params={"access_token": resolved["token"], "limit": 300},
            timeout=15,
        )
        if not response.ok:
            return Response(
                {"success": False, "error": "Failed to fetch templates from Meta.", "details": _meta_error(response)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        payload = response.json()
        return Response(
            {"success": True, "templates": payload.get("data") or [], "waba_id": waba.waba_id},
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        if not self._authorize(request):
            return Response({"success": False, "error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)

        resolved, error = self._resolve_account(request, request.data)
        if error:
            return error

        name = request.data.get("name")
        category = request.data.get("category")
        language = request.data.get("language")
        components = request.data.get("components")
        if not name or not category or not language or not components:
            return Response(
                {"success": False, "error": "Missing required fields: name, category, language, components."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        button_components = [component for component in components if component.get("type") == "BUTTONS"]
        if sum(len(component.get("buttons") or []) for component in button_components) > 10:
            return Response({"success": False, "error": "Meta supports a maximum of 10 buttons per template."}, status=status.HTTP_400_BAD_REQUEST)

        waba = resolved["waba"]
        response = requests.post(
            f"{GRAPH_API_BASE}/{waba.waba_id}/message_templates",
            params={"access_token": resolved["token"]},
            json={
                "name": name,
                "category": category,
                "language": str(language).strip(),
                "components": components,
            },
            timeout=15,
        )
        if not response.ok:
            return Response(
                {"success": False, "error": "Failed to create template on Meta.", "details": _meta_error(response)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response({"success": True, "data": response.json(), "waba_id": waba.waba_id}, status=status.HTTP_200_OK)

    def patch(self, request):
        if not self._authorize(request):
            return Response({"success": False, "error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)

        template_id = request.data.get("template_id") or request.data.get("id")
        if not template_id:
            return Response({"success": False, "error": "template_id is required to update a template."}, status=status.HTTP_400_BAD_REQUEST)

        resolved, error = self._resolve_account(request, request.data)
        if error:
            return error

        components = request.data.get("components")
        category = request.data.get("category")
        if not components:
            return Response({"success": False, "error": "components are required to update a template."}, status=status.HTTP_400_BAD_REQUEST)
        button_components = [component for component in components if component.get("type") == "BUTTONS"]
        if sum(len(component.get("buttons") or []) for component in button_components) > 10:
            return Response({"success": False, "error": "Meta supports a maximum of 10 buttons per template."}, status=status.HTTP_400_BAD_REQUEST)

        payload = {"components": components}
        if category:
            payload["category"] = category

        response = requests.post(
            f"{GRAPH_API_BASE}/{template_id}",
            params={"access_token": resolved["token"]},
            json=payload,
            timeout=15,
        )
        if not response.ok:
            return Response(
                {"success": False, "error": "Failed to update template on Meta.", "details": _meta_error(response)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response({"success": True, "data": response.json(), "waba_id": resolved["waba"].waba_id}, status=status.HTTP_200_OK)

    def delete(self, request):
        if not self._authorize(request):
            return Response({"success": False, "error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)

        template_id = request.query_params.get("template_id") or request.data.get("template_id")
        template_name = request.query_params.get("name") or request.data.get("name")
        if not template_id and not template_name:
            return Response({"success": False, "error": "template_id or name is required to delete a template."}, status=status.HTTP_400_BAD_REQUEST)

        resolved, error = self._resolve_account(request, request.data)
        if error:
            return error

        params = {"access_token": resolved["token"]}
        # Prefer WABA-scoped deletion by name. Supplying hsm_id makes Meta
        # perform an additional object-level ownership check which can reject
        # otherwise valid WABA tokens with error #100.
        if template_name:
            params["name"] = template_name
        elif template_id:
            params["hsm_id"] = template_id

        response = requests.delete(
            f"{GRAPH_API_BASE}/{resolved['waba'].waba_id}/message_templates",
            params=params,
            timeout=15,
        )
        if not response.ok:
            return Response(
                {"success": False, "error": "Failed to delete template on Meta.", "details": _meta_error(response)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response({"success": True, "data": response.json() if response.content else {}, "waba_id": resolved["waba"].waba_id}, status=status.HTTP_200_OK)
