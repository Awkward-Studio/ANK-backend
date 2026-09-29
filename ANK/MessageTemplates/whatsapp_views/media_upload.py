import logging
import os
import re

import requests
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from MessageTemplates.services.whatsapp import WhatsAppError, _get_credentials


logger = logging.getLogger(__name__)
GRAPH_API_VERSION = os.getenv("META_GRAPH_API_VERSION", "v25.0")
GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

MEDIA_TYPES = {
    "image/jpeg": ("image", 5 * 1024 * 1024),
    "image/png": ("image", 5 * 1024 * 1024),
    "video/mp4": ("video", 16 * 1024 * 1024),
    "video/3gpp": ("video", 16 * 1024 * 1024),
    "video/3gp": ("video", 16 * 1024 * 1024),
    "audio/aac": ("audio", 16 * 1024 * 1024),
    "audio/amr": ("audio", 16 * 1024 * 1024),
    "audio/mpeg": ("audio", 16 * 1024 * 1024),
    "audio/mp4": ("audio", 16 * 1024 * 1024),
    "audio/ogg": ("audio", 16 * 1024 * 1024),
    "text/plain": ("document", 100 * 1024 * 1024),
    "application/pdf": ("document", 100 * 1024 * 1024),
    "application/msword": ("document", 100 * 1024 * 1024),
    "application/vnd.ms-excel": ("document", 100 * 1024 * 1024),
    "application/vnd.ms-powerpoint": ("document", 100 * 1024 * 1024),
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": (
        "document",
        100 * 1024 * 1024,
    ),
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": (
        "document",
        100 * 1024 * 1024,
    ),
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": (
        "document",
        100 * 1024 * 1024,
    ),
}


def _safe_filename(name: str) -> str:
    basename = os.path.basename(name or "upload")
    return re.sub(r"[^a-zA-Z0-9._-]", "_", basename)


def _meta_error(response: requests.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return (response.text or "Meta rejected the media upload.")[:300]

    error = payload.get("error") or {}
    return (
        error.get("error_user_msg")
        or error.get("message")
        or "Meta rejected the media upload."
    )


class WhatsAppMediaUploadView(APIView):
    """Relay one authenticated media upload directly to Meta.

    The uploaded file only lives for the duration of this request. This avoids
    coordinating chunks through an Amplify instance's non-shared /tmp folder.
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        uploaded_file = request.FILES.get("file")
        if not uploaded_file:
            return Response({"ok": False, "error": "No file provided"}, status=status.HTTP_400_BAD_REQUEST)

        content_type = str(uploaded_file.content_type or "").lower()
        media_config = MEDIA_TYPES.get(content_type)
        if not media_config:
            return Response(
                {"ok": False, "error": f"Unsupported file type: {content_type or 'unknown'}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        media_type, max_size = media_config
        if uploaded_file.size > max_size:
            return Response(
                {
                    "ok": False,
                    "error": f"File too large. Max size for {media_type}: {max_size // (1024 * 1024)}MB",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        requested_phone_number_id = request.data.get("phone_number_id") or None
        try:
            access_token, phone_number_id = _get_credentials(requested_phone_number_id)
        except WhatsAppError as exc:
            return Response({"ok": False, "error": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        safe_name = _safe_filename(uploaded_file.name)
        try:
            uploaded_file.seek(0)
            upload_response = requests.post(
                f"{GRAPH_API_BASE}/{phone_number_id}/media",
                headers={"Authorization": f"Bearer {access_token}"},
                data={"messaging_product": "whatsapp"},
                files={"file": (safe_name, uploaded_file, content_type)},
                timeout=(10, 120),
            )
        except requests.RequestException as exc:
            logger.exception("WhatsApp media upload request failed")
            return Response(
                {"ok": False, "error": f"Could not upload media to Meta: {exc}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        if upload_response.status_code >= 300:
            return Response(
                {"ok": False, "error": _meta_error(upload_response)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        try:
            media_id = upload_response.json().get("id")
        except ValueError:
            media_id = None
        if not media_id:
            return Response(
                {"ok": False, "error": "Meta did not return a media ID"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        media_url = None
        try:
            url_response = requests.get(
                f"{GRAPH_API_BASE}/{media_id}",
                params={"phone_number_id": phone_number_id},
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=(10, 30),
            )
            if url_response.status_code < 300:
                media_url = url_response.json().get("url")
        except (requests.RequestException, ValueError):
            # The media ID is sufficient for sending. URL lookup is optional.
            pass

        return Response(
            {
                "ok": True,
                "mediaId": media_id,
                "mediaUrl": media_url,
                "mediaType": media_type,
            },
            status=status.HTTP_200_OK,
        )
