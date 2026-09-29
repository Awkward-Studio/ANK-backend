import logging
import os
import re
from uuid import uuid4

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
META_TEMPLATE_TIMEOUT = (10, 30)
RETRYABLE_META_STATUSES = {429, 500, 502, 503, 504}


def _meta_error(response: requests.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text[:300]
    if not isinstance(payload, dict):
        return "Meta returned an invalid response."
    error = payload.get("error") or {}
    if not isinstance(error, dict):
        return str(error)[:300]
    return error.get("error_user_msg") or error.get("message") or response.text[:300]


def _meta_json(response: requests.Response) -> dict:
    try:
        payload = response.json()
    except ValueError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _meta_request(method: str, url: str, *, retry_safe: bool = False, **kwargs) -> requests.Response:
    """Call Meta, retrying only operations that are safe to repeat."""
    attempts = 2 if retry_safe else 1
    request_fn = getattr(requests, method.lower())
    for attempt in range(attempts):
        try:
            response = request_fn(url, timeout=META_TEMPLATE_TIMEOUT, **kwargs)
        except requests.RequestException:
            if attempt + 1 < attempts:
                continue
            raise
        if response.status_code in RETRYABLE_META_STATUSES and attempt + 1 < attempts:
            continue
        return response
    raise requests.RequestException("Meta request did not complete")


def _validate_components(components, *, require_media_handle: bool = True) -> str:
    if not isinstance(components, list) or not components:
        return "components must be a non-empty list."
    if any(not isinstance(component, dict) for component in components):
        return "Every template component must be an object."

    bodies = [component for component in components if component.get("type") == "BODY"]
    if len(bodies) != 1 or not str(bodies[0].get("text") or "").strip():
        return "Exactly one non-empty BODY component is required."
    body_text = str(bodies[0]["text"])
    if re.match(r"^\s*\{\{\d+\}\}", body_text) or re.search(r"\{\{\d+\}\}\s*$", body_text):
        return "Body variables cannot be the first or last content in the message."
    indexes = sorted({int(value) for value in re.findall(r"\{\{(\d+)\}\}", body_text)})
    if indexes and indexes != list(range(1, max(indexes) + 1)):
        return "Body variables must be sequential, starting with {{1}}."

    headers = [component for component in components if component.get("type") == "HEADER"]
    if len(headers) > 1:
        return "Only one HEADER component is allowed."
    if headers:
        header = headers[0]
        header_format = str(header.get("format") or "").upper()
        if header_format == "TEXT" and not str(header.get("text") or "").strip():
            return "A text header cannot be empty."
        if require_media_handle and header_format in {"IMAGE", "VIDEO", "DOCUMENT"}:
            handles = (header.get("example") or {}).get("header_handle") or []
            if not isinstance(handles, list) or not handles or not handles[0]:
                return f"A verified {header_format.lower()} header upload is required."

    buttons = [
        button
        for component in components
        if component.get("type") == "BUTTONS"
        for button in (component.get("buttons") or [])
    ]
    if len(buttons) > 10:
        return "Meta supports a maximum of 10 buttons per template."
    for button in buttons:
        if not isinstance(button, dict) or not str(button.get("text") or "").strip():
            return "Every button requires a label."
        if button.get("type") == "URL" and not str(button.get("url") or "").strip():
            return "Every URL button requires a URL."
        if button.get("type") == "PHONE_NUMBER" and not str(button.get("phone_number") or "").strip():
            return "Every phone button requires a phone number."
    return ""


class WhatsAppTemplateManagementView(APIView):
    permission_classes = [AllowAny]

    def _authorize(self, request) -> bool:
        token = request.headers.get("X-Webhook-Token", "")
        return bool(WEBHOOK_SECRET and token == WEBHOOK_SECRET)

    @staticmethod
    def _request_id(request) -> str:
        return request.headers.get("X-Request-ID") or str(uuid4())

    @staticmethod
    def _meta_failure(operation: str, response: requests.Response, request_id: str) -> Response:
        retryable = response.status_code in RETRYABLE_META_STATUSES
        logger.warning(
            "[WHATSAPP_TEMPLATE] %s failed request_id=%s meta_status=%s details=%s",
            operation,
            request_id,
            response.status_code,
            _meta_error(response),
        )
        return Response(
            {
                "success": False,
                "error": f"Meta could not {operation}.",
                "details": _meta_error(response),
                "code": "META_TRANSIENT_ERROR" if retryable else "META_REJECTED",
                "retryable": retryable,
                "request_id": request_id,
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE if retryable else status.HTTP_502_BAD_GATEWAY,
        )

    @staticmethod
    def _transport_failure(operation: str, exc: requests.RequestException, request_id: str) -> Response:
        logger.exception(
            "[WHATSAPP_TEMPLATE] %s transport failure request_id=%s",
            operation,
            request_id,
        )
        return Response(
            {
                "success": False,
                "error": f"Could not reach Meta to {operation}.",
                "details": str(exc),
                "code": "META_UNREACHABLE",
                "retryable": True,
                "request_id": request_id,
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

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

        request_id = self._request_id(request)
        waba = resolved["waba"]
        try:
            response = _meta_request(
                "get",
                f"{GRAPH_API_BASE}/{waba.waba_id}/message_templates",
                params={"access_token": resolved["token"], "limit": 300},
                retry_safe=True,
            )
        except requests.RequestException as exc:
            return self._transport_failure("fetch templates", exc, request_id)
        if not response.ok:
            return self._meta_failure("fetch templates", response, request_id)

        payload = _meta_json(response)
        return Response(
            {
                "success": True,
                "templates": payload.get("data") or [],
                "waba_id": waba.waba_id,
                "request_id": request_id,
            },
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
        component_error = _validate_components(components)
        if component_error:
            return Response({"success": False, "error": component_error}, status=status.HTTP_400_BAD_REQUEST)

        request_id = self._request_id(request)
        waba = resolved["waba"]
        try:
            response = _meta_request(
                "post",
                f"{GRAPH_API_BASE}/{waba.waba_id}/message_templates",
                params={"access_token": resolved["token"]},
                json={
                    "name": name,
                    "category": category,
                    "language": str(language).strip(),
                    "components": components,
                },
            )
        except requests.RequestException as exc:
            return self._transport_failure("create template", exc, request_id)
        if not response.ok:
            return self._meta_failure("create template", response, request_id)

        return Response({"success": True, "data": _meta_json(response), "waba_id": waba.waba_id, "request_id": request_id}, status=status.HTTP_200_OK)

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
        component_error = _validate_components(components, require_media_handle=False)
        if component_error:
            return Response({"success": False, "error": component_error}, status=status.HTTP_400_BAD_REQUEST)

        payload = {"components": components}
        if category:
            payload["category"] = category

        request_id = self._request_id(request)
        try:
            response = _meta_request(
                "post",
                f"{GRAPH_API_BASE}/{template_id}",
                params={"access_token": resolved["token"]},
                json=payload,
            )
        except requests.RequestException as exc:
            return self._transport_failure("update template", exc, request_id)
        if not response.ok:
            return self._meta_failure("update template", response, request_id)

        return Response({"success": True, "data": _meta_json(response), "waba_id": resolved["waba"].waba_id, "request_id": request_id}, status=status.HTTP_200_OK)

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

        request_id = self._request_id(request)
        try:
            response = _meta_request(
                "delete",
                f"{GRAPH_API_BASE}/{resolved['waba'].waba_id}/message_templates",
                params=params,
            )
        except requests.RequestException as exc:
            return self._transport_failure("delete template", exc, request_id)
        if not response.ok:
            return self._meta_failure("delete template", response, request_id)

        return Response({"success": True, "data": _meta_json(response) if response.content else {}, "waba_id": resolved["waba"].waba_id, "request_id": request_id}, status=status.HTTP_200_OK)
