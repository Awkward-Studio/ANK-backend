import base64
import hashlib
import hmac
import io
import json
import logging
import os
import re
import uuid

import qrcode
import requests
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.conf import settings
from django.http import HttpResponseForbidden, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from Events.models.event_model import Event
from Events.models.event_registration_model import EventRegistration
from Events.models.session_registration import SessionRegistration
from MessageTemplates.models import (
    BroadcastCampaign,
    BroadcastRecipient,
    QrTemplateConfig,
    QrTicket,
    MessageTemplate,
    WhatsAppPhoneNumber,
)
from MessageTemplates.services.whatsapp import WhatsAppError, _get_credentials


logger = logging.getLogger("whatsapp")
GRAPH_API_VERSION = os.getenv("META_GRAPH_API_VERSION", "v25.0")
GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"
SECURITY_TOKEN_PREFIX = "ANKSEC1:"
SENSITIVE_DETAIL_KEY = re.compile(
    r"password|secret|token|bank|account|ifsc|aadhaar|aadhar|pan(?:_|\s)*(?:number|no)?|passport|photo(?:_|\s)*id",
    re.IGNORECASE,
)


def _existing_pk(model, value):
    if not value:
        return None
    try:
        return model.objects.filter(pk=value).values_list("pk", flat=True).first()
    except (TypeError, ValueError):
        return None


def _get_encryption_key(secret_override=None):
    secret = (
        secret_override
        or os.getenv("SECURITY_QR_SECRET")
        or os.getenv("DJANGO_RSVP_SECRET")
        or getattr(settings, "SECRET_KEY", "ank-security-qr-secret-key-32b")
    )
    return hashlib.sha256(secret.encode("utf-8")).digest()


def encrypt_security_qr_payload(payload: dict, secret_override=None) -> str:
    """Encrypt dynamic QR payload with AES-256-GCM so only the security module can view it."""
    key = _get_encryption_key(secret_override)
    aesgcm = AESGCM(key)
    iv = os.urandom(12)
    plaintext = json.dumps(payload, separators=(",", ":"), ensure_ascii=False, sort_keys=True).encode("utf-8")
    ct_with_tag = aesgcm.encrypt(iv, plaintext, None)
    iv_b64 = base64.urlsafe_b64encode(iv).decode("ascii").rstrip("=")
    ct_b64 = base64.urlsafe_b64encode(ct_with_tag).decode("ascii").rstrip("=")
    return f"{SECURITY_TOKEN_PREFIX}{iv_b64}.{ct_b64}"


def decrypt_security_qr_payload(token: str, secret_override=None) -> dict:
    """Decrypt and verify an AES-256-GCM security QR token."""
    token = str(token or "").strip()
    if not token.startswith(SECURITY_TOKEN_PREFIX):
        raise ValueError("Invalid security QR code prefix: must start with ANKSEC1:")
    body = token[len(SECURITY_TOKEN_PREFIX):]
    parts = body.split(".")
    if len(parts) != 2:
        raise ValueError("Malformed security QR token structure")
    iv_b64, ct_b64 = parts

    def _pad_b64(s: str) -> str:
        return s + "=" * (-len(s) % 4)

    iv = base64.urlsafe_b64decode(_pad_b64(iv_b64))
    ct_with_tag = base64.urlsafe_b64decode(_pad_b64(ct_b64))
    if len(iv) != 12:
        raise ValueError("Invalid IV length for AES-GCM")
    key = _get_encryption_key(secret_override)
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(iv, ct_with_tag, None)
    return json.loads(plaintext.decode("utf-8"))


def _has_internal_access(request):
    expected = os.getenv("DJANGO_RSVP_SECRET", "")
    supplied = request.headers.get("X-Webhook-Token", "")
    return bool(expected and supplied and hmac.compare_digest(expected, supplied))


def _json_body(request):
    try:
        value = json.loads(request.body.decode("utf-8"))
        return value if isinstance(value, dict) else None
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


def _clean_details(raw):
    if not isinstance(raw, dict):
        return {}

    cleaned = {}
    for key, value in list(raw.items())[:50]:
        label = str(key).strip()[:80]
        if not label or SENSITIVE_DETAIL_KEY.search(label):
            continue
        if value is None or isinstance(value, (dict, list, tuple, set)):
            continue
        text = str(value).strip()
        if text:
            cleaned[label] = text[:120]
    return dict(list(cleaned.items())[:10])


def _qr_png(content):
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=12,
        border=4,
    )
    qr.add_data(content)
    qr.make(fit=True)
    image = qr.make_image(fill_color="#171411", back_color="#ffffff")
    output = io.BytesIO()
    image.save(output, format="PNG")
    output.seek(0)
    return output


def _is_qr_enabled_template(template_name, sender_phone_number_id):
    return QrTemplateConfig.objects.filter(
        phone_number_id=sender_phone_number_id,
        template_name=template_name,
        is_qr_template=True,
    ).exists() or MessageTemplate.objects.filter(
        name=template_name,
        is_qr_template=True,
    ).exists()


def _upload_qr_to_meta(png, token, resolved_sender_id):
    response = requests.post(
        f"{GRAPH_API_BASE}/{resolved_sender_id}/media",
        headers={"Authorization": f"Bearer {token}"},
        data={"messaging_product": "whatsapp"},
        files={"file": ("dynamic-qr-test.png", png, "image/png")},
        timeout=(15, 120),
    )
    if response.status_code >= 300:
        try:
            error = response.json().get("error", {}).get("message")
        except (ValueError, AttributeError):
            error = None
        raise WhatsAppError(error or "Meta rejected the generated QR image")
    try:
        media_id = response.json().get("id")
    except (ValueError, AttributeError) as exc:
        raise WhatsAppError("Meta did not return a media ID for the QR image") from exc
    if not media_id:
        raise WhatsAppError("Meta did not return a media ID for the QR image")
    return str(media_id)


@csrf_exempt
@require_http_methods(["POST"])
def issue_qr_test_media(request):
    """Generate an encrypted, recipient-bound QR ticket and persist its audit record."""
    if not _has_internal_access(request):
        return HttpResponseForbidden("invalid token")

    body = _json_body(request)
    if body is None:
        return JsonResponse({"ok": False, "error": "invalid json"}, status=400)

    recipient_name = str(body.get("recipient_name") or body.get("guest_name") or "Guest").strip()
    recipient_phone = str(body.get("recipient_phone") or body.get("phone") or "").strip()
    sender_phone_number_id = str(body.get("sender_phone_number_id") or "").strip()
    template_name = str(body.get("template_name") or "").strip()
    template_language = str(body.get("template_language") or "en_US").strip()
    if not _is_qr_enabled_template(template_name, sender_phone_number_id):
        return JsonResponse({"ok": False, "error": "The selected template is not marked as a QR template."}, status=400)
    if not recipient_phone or not sender_phone_number_id:
        return JsonResponse(
            {"ok": False, "error": "recipient_phone and sender_phone_number_id are required"},
            status=400,
        )
    ticket_id = uuid.uuid4()
    payload = {
        "type": "ank_dynamic_qr_test",
        "test_id": str(ticket_id),
        "qr_ticket_id": str(ticket_id),
        "template": template_name,
        "template_language": template_language,
        "generated_at": timezone.now().isoformat(),
        "recipient": {
            "name": recipient_name[:255] or "Guest",
            "phone": recipient_phone[:32],
        },
        "data": _clean_details(body.get("details") or {}),
        "random_code": uuid.uuid4().hex[:12],
    }
    for field in ("registration_id", "event_registration_id", "session_registration_id", "event_id", "session_id", "guest_id", "uid"):
        if body.get(field):
            payload[field] = str(body[field])
    if body.get("registration_id") and not body.get("event_registration_id"):
        payload["event_registration_id"] = str(body["registration_id"])
    encrypted_token = encrypt_security_qr_payload(payload)

    try:
        access_token, resolved_sender_id = _get_credentials(sender_phone_number_id)
        media_id = _upload_qr_to_meta(_qr_png(encrypted_token), access_token, resolved_sender_id)
    except (WhatsAppError, requests.RequestException) as exc:
        logger.exception("Could not generate QR test media for %s", recipient_phone)
        return JsonResponse({"ok": False, "error": str(exc)}, status=502)

    event_registration_id = payload.get("event_registration_id")
    session_registration_id = payload.get("session_registration_id")
    campaign_id = body.get("campaign_id")
    campaign_recipient_id = body.get("campaign_recipient_id")
    event_id = payload.get("event_id")
    event_registration_pk = _existing_pk(EventRegistration, event_registration_id)
    session_registration_pk = _existing_pk(SessionRegistration, session_registration_id)
    event_pk = _existing_pk(Event, event_id)
    campaign_pk = _existing_pk(BroadcastCampaign, campaign_id)
    campaign_recipient_pk = _existing_pk(BroadcastRecipient, campaign_recipient_id)
    if not event_pk and event_registration_pk:
        event_pk = EventRegistration.objects.filter(pk=event_registration_pk).values_list("event_id", flat=True).first()
    if not event_registration_pk and session_registration_pk:
        session_registration = SessionRegistration.objects.select_related("session").filter(pk=session_registration_pk).first()
        if session_registration:
            event_registration_pk = EventRegistration.objects.filter(
                guest_id=session_registration.guest_id,
                event_id=session_registration.session.event_id,
            ).values_list("id", flat=True).first()
            event_pk = event_pk or session_registration.session.event_id
    ticket = QrTicket.objects.create(
        id=ticket_id,
        template_name=template_name,
        template_language=template_language,
        sender_phone_number_id=sender_phone_number_id,
        recipient_phone=recipient_phone[:50],
        recipient_name=recipient_name[:255],
        media_id=media_id,
        token_digest=hashlib.sha256(encrypted_token.encode("utf-8")).hexdigest(),
        event_id=event_pk,
        event_registration_id=event_registration_pk,
        session_registration_id=session_registration_pk,
        campaign_id=campaign_pk,
        campaign_recipient_id=campaign_recipient_pk,
    )

    return JsonResponse(
        {
            "ok": True,
            "media_id": media_id,
            "test_id": str(ticket.id),
            "ticket_id": str(ticket.id),
            "qr_token": encrypted_token,
            "qr_payload": payload,
        },
        status=201,
    )


@csrf_exempt
@require_http_methods(["POST"])
def verify_qr_test_media(request):
    """Decrypt and verify security QR payload. Accessible internally by the security module."""
    if not _has_internal_access(request):
        return HttpResponseForbidden("invalid token")

    body = _json_body(request)
    if body is None:
        return JsonResponse({"ok": False, "error": "invalid json"}, status=400)

    token = str(body.get("token") or body.get("qr_text") or "").strip()
    if not token:
        return JsonResponse({"ok": False, "valid": False, "error": "token is required"}, status=400)

    try:
        payload = decrypt_security_qr_payload(token)
        return JsonResponse(
            {
                "ok": True,
                "valid": True,
                "payload": payload,
                "verified_at": timezone.now().isoformat(),
            },
            status=200,
        )
    except Exception as exc:
        logger.warning("Failed to decrypt security QR pass: %s", exc)
        return JsonResponse(
            {
                "ok": True,
                "valid": False,
                "error": "This QR code is not a valid security pass or has been altered",
            },
            status=200,
        )
