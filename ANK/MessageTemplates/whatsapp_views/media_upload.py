import logging
import os
import re
import tempfile
import time
from contextlib import contextmanager

import requests
from django.conf import settings
from filelock import FileLock, Timeout as FileLockTimeout
from requests_toolbelt.multipart.encoder import MultipartEncoder
from urllib3.util import Timeout
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from MessageTemplates.services.whatsapp import WhatsAppError, _get_credentials


logger = logging.getLogger(__name__)
GRAPH_API_VERSION = os.getenv("META_GRAPH_API_VERSION", "v25.0")
GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"
MAX_DOCUMENT_SIZE = 100 * 1024 * 1024

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
    "text/plain": ("document", MAX_DOCUMENT_SIZE),
    "application/pdf": ("document", MAX_DOCUMENT_SIZE),
    "application/msword": ("document", MAX_DOCUMENT_SIZE),
    "application/vnd.ms-excel": ("document", MAX_DOCUMENT_SIZE),
    "application/vnd.ms-powerpoint": ("document", MAX_DOCUMENT_SIZE),
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": (
        "document",
        MAX_DOCUMENT_SIZE,
    ),
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": (
        "document",
        MAX_DOCUMENT_SIZE,
    ),
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": (
        "document",
        MAX_DOCUMENT_SIZE,
    ),
}

MEDIA_TYPES_BY_EXTENSION = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".mp4": "video/mp4",
    ".3gp": "video/3gpp",
    ".aac": "audio/aac",
    ".amr": "audio/amr",
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".ogg": "audio/ogg",
    ".txt": "text/plain",
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".xls": "application/vnd.ms-excel",
    ".ppt": "application/vnd.ms-powerpoint",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}

RETRYABLE_META_STATUSES = {429, 500, 502, 503, 504}
META_UPLOAD_TIMEOUT = (15, 180)
# Leave time for a response before the ALB's 300-second idle timeout.
META_UPLOAD_BUDGET_SECONDS = 210


@contextmanager
def _upload_slot():
    """Bound uploads across threads and processes sharing this container's /tmp."""
    lock = None
    for slot in range(settings.WHATSAPP_MEDIA_MAX_CONCURRENT_UPLOADS):
        candidate = FileLock(os.path.join(
            tempfile.gettempdir(), f"ank-whatsapp-upload-{slot}.lock"
        ))
        try:
            candidate.acquire(timeout=0)
        except FileLockTimeout:
            continue
        lock = candidate
        break
    try:
        yield lock is not None
    finally:
        if lock is not None:
            lock.release()


class _UploadStream:
    """A sized request body with bounded reads and a transfer deadline."""

    def __init__(self, body, size, deadline):
        self.body = body
        self.len = size
        self.deadline = deadline

    def read(self, size=-1):
        if time.monotonic() >= self.deadline:
            raise requests.Timeout("WhatsApp media upload exceeded its time limit")
        return self.body.read(min(size, 64 * 1024) if size >= 0 else 64 * 1024)


def _remaining_timeout(deadline, timeout):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise requests.Timeout("WhatsApp media upload exceeded its time limit")
    # urllib3 accounts for time spent connecting and sending before it chooses
    # the response read timeout. A tuple would restart the full read timeout
    # after a slow transfer had already consumed most of our request budget.
    return Timeout(
        total=remaining,
        connect=min(timeout[0], remaining),
        read=min(timeout[1], remaining),
    )


def _message_upload_body(uploaded_file, safe_name, content_type, deadline):
    # Pass the underlying file. UploadedFile.__len__ reports the original size,
    # whereas the encoder needs the remaining size as it consumes each part.
    encoder = MultipartEncoder(fields={
        "messaging_product": "whatsapp",
        "file": (safe_name, uploaded_file.file, content_type),
    })
    return _UploadStream(encoder, encoder.len, deadline), encoder.content_type


def _safe_filename(name: str) -> str:
    basename = os.path.basename(name or "upload")
    return re.sub(r"[^a-zA-Z0-9._-]", "_", basename)


def _meta_error(response: requests.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return (response.text or "Meta rejected the media upload.")[:300]

    if not isinstance(payload, dict):
        return "Meta rejected the media upload."

    error = payload.get("error") or {}
    if not isinstance(error, dict):
        return str(error)[:300]
    return (
        error.get("error_user_msg")
        or error.get("message")
        or "Meta rejected the media upload."
    )


def _resolve_media_config(uploaded_file):
    content_type = str(uploaded_file.content_type or "").lower().split(";", 1)[0].strip()
    if content_type not in MEDIA_TYPES and content_type in {"", "application/octet-stream"}:
        extension = os.path.splitext(uploaded_file.name or "")[1].lower()
        content_type = MEDIA_TYPES_BY_EXTENSION.get(extension, content_type)
    return content_type, MEDIA_TYPES.get(content_type)


def _post_with_retry(url, *, rewind_file=None, body_factory=None, deadline=None, **kwargs):
    """Retry one transient Meta failure while safely rewinding the upload."""
    last_response = None
    for attempt in range(2):
        if rewind_file is not None:
            rewind_file.seek(0)
        attempt_kwargs = dict(kwargs)
        if deadline is not None:
            attempt_kwargs["timeout"] = _remaining_timeout(deadline, kwargs["timeout"])
        if body_factory is not None:
            body, content_type = body_factory()
            attempt_kwargs["data"] = body
            attempt_kwargs["headers"] = {**kwargs.get("headers", {}), "Content-Type": content_type}
        try:
            response = requests.post(url, **attempt_kwargs)
        except requests.RequestException:
            if attempt == 0:
                continue
            raise
        last_response = response
        if response.status_code not in RETRYABLE_META_STATUSES or attempt == 1:
            return response
    return last_response


def _get_meta_app_id(access_token: str, deadline) -> str:
    configured_app_id = os.getenv("META_APP_ID") or os.getenv("FACEBOOK_APP_ID")
    if configured_app_id:
        return configured_app_id

    response = requests.get(
        f"{GRAPH_API_BASE}/debug_token",
        params={"input_token": access_token, "access_token": access_token},
        timeout=_remaining_timeout(deadline, (10, 30)),
    )
    if response.status_code >= 300:
        raise WhatsAppError(_meta_error(response))
    try:
        payload = response.json()
    except ValueError as exc:
        raise WhatsAppError("Meta did not return an app ID for the upload.") from exc
    app_id = payload.get("data", {}).get("app_id") if isinstance(payload, dict) else None
    if not app_id:
        raise WhatsAppError("Could not determine the Meta app ID for the upload.")
    return str(app_id)


def _upload_template_media(uploaded_file, safe_name, content_type, access_token, deadline):
    """Upload a template example and return Meta's required header handle."""
    app_id = _get_meta_app_id(access_token, deadline)

    # If the raw upload suffers a transient failure, create a fresh session before
    # retrying. Reusing an uncertain session at offset zero can corrupt its state.
    last_response = None
    for attempt in range(2):
        session_response = _post_with_retry(
            f"{GRAPH_API_BASE}/{app_id}/uploads",
            params={
                "file_length": uploaded_file.size,
                "file_type": content_type,
                "file_name": safe_name,
            },
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=(10, 45),
            deadline=deadline,
        )
        if session_response.status_code >= 300:
            return session_response, None
        try:
            session_payload = session_response.json()
        except ValueError:
            return session_response, None
        upload_session_id = session_payload.get("id") if isinstance(session_payload, dict) else None
        if not upload_session_id:
            return session_response, None

        uploaded_file.seek(0)
        try:
            upload_response = requests.post(
                f"{GRAPH_API_BASE}/{upload_session_id}",
                headers={
                    "Authorization": f"OAuth {access_token}",
                    "Content-Type": content_type,
                    "Content-Length": str(uploaded_file.size),
                    "file_offset": "0",
                },
                data=_UploadStream(uploaded_file, uploaded_file.size, deadline),
                timeout=_remaining_timeout(deadline, META_UPLOAD_TIMEOUT),
            )
        except requests.RequestException:
            if attempt == 0:
                continue
            raise

        last_response = upload_response
        if upload_response.status_code in RETRYABLE_META_STATUSES and attempt == 0:
            continue
        try:
            upload_payload = upload_response.json()
        except ValueError:
            upload_payload = {}
        header_handle = upload_payload.get("h") if isinstance(upload_payload, dict) else None
        return upload_response, header_handle

    return last_response, None


class WhatsAppMediaUploadView(APIView):
    """Relay one authenticated media upload directly to Meta.

    The uploaded file only lives for the duration of this request. This avoids
    coordinating chunks through an Amplify instance's non-shared /tmp folder.
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        with _upload_slot() as acquired:
            if not acquired:
                return Response(
                    {"ok": False, "error": "Another media upload is in progress. Please try again shortly."},
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                    headers={"Retry-After": "10"},
                )
            return self._upload(request)

    def _upload(self, request):
        uploaded_file = request.FILES.get("file")
        if not uploaded_file:
            return Response({"ok": False, "error": "No file provided"}, status=status.HTTP_400_BAD_REQUEST)

        if uploaded_file.size <= 0:
            return Response({"ok": False, "error": "The selected file is empty"}, status=status.HTTP_400_BAD_REQUEST)

        content_type, media_config = _resolve_media_config(uploaded_file)
        if not media_config:
            return Response(
                {"ok": False, "error": f"Unsupported file type: {content_type or 'unknown'}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        media_type, max_size = media_config
        if uploaded_file.size > max_size:
            max_mb = max_size // (1024 * 1024)
            return Response(
                {
                    "ok": False,
                    "error": f"File too large. Max size for {media_type}: {max_mb}MB",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        requested_phone_number_id = request.data.get("phone_number_id") or None
        try:
            access_token, phone_number_id = _get_credentials(requested_phone_number_id)
        except WhatsAppError as exc:
            return Response({"ok": False, "error": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        safe_name = _safe_filename(uploaded_file.name)
        upload_type = str(request.data.get("upload_type") or "message").lower()
        if upload_type not in {"message", "template"}:
            return Response({"ok": False, "error": "Invalid upload type"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            deadline = time.monotonic() + META_UPLOAD_BUDGET_SECONDS
            if upload_type == "template":
                upload_response, header_handle = _upload_template_media(
                    uploaded_file, safe_name, content_type, access_token, deadline
                )
            else:
                header_handle = None
                upload_response = _post_with_retry(
                    f"{GRAPH_API_BASE}/{phone_number_id}/media",
                    headers={"Authorization": f"Bearer {access_token}"},
                    body_factory=lambda: _message_upload_body(
                        uploaded_file, safe_name, content_type, deadline
                    ),
                    timeout=META_UPLOAD_TIMEOUT,
                    rewind_file=uploaded_file,
                    deadline=deadline,
                )
        except (requests.RequestException, WhatsAppError) as exc:
            logger.warning(
                "WhatsApp media upload failed: type=%s bytes=%s error=%s",
                media_type, uploaded_file.size, type(exc).__name__,
            )
            return Response(
                {"ok": False, "error": "Could not upload media to WhatsApp. Please try again on a stable connection."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        if upload_response.status_code >= 300:
            logger.warning(
                "WhatsApp media upload rejected: type=%s bytes=%s meta_status=%s",
                media_type, uploaded_file.size, upload_response.status_code,
            )
            return Response(
                {"ok": False, "error": (
                    "WhatsApp rejected the file size. Please choose a smaller file."
                    if upload_response.status_code == 413 else _meta_error(upload_response)
                )},
                status=(
                    status.HTTP_400_BAD_REQUEST if upload_response.status_code == 413
                    else status.HTTP_502_BAD_GATEWAY
                ),
            )

        if upload_type == "template":
            if not header_handle:
                return Response(
                    {"ok": False, "error": "Meta did not return a template header handle"},
                    status=status.HTTP_502_BAD_GATEWAY,
                )
            return Response(
                {
                    "ok": True,
                    "mediaId": header_handle,
                    "headerHandle": header_handle,
                    "mediaUrl": None,
                    "mediaType": media_type,
                },
                status=status.HTTP_200_OK,
            )

        try:
            upload_payload = upload_response.json()
        except ValueError:
            upload_payload = {}
        media_id = upload_payload.get("id") if isinstance(upload_payload, dict) else None
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
                timeout=_remaining_timeout(deadline, (10, 30)),
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
