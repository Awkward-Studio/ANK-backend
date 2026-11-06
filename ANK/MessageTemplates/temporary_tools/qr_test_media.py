import hmac
import io
import json
import logging
import os
import re
import uuid

import qrcode
import requests
from django.http import HttpResponseForbidden, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from MessageTemplates.models import WhatsAppPhoneNumber
from MessageTemplates.services.whatsapp import WhatsAppError, _get_credentials


logger = logging.getLogger("whatsapp")
GRAPH_API_VERSION = os.getenv("META_GRAPH_API_VERSION", "v25.0")
GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"
QR_TEMPLATE_NAME = "qr_image_bulksend_test"
QR_TEST_SENDER_SUFFIX = "00792"
SENSITIVE_DETAIL_KEY = re.compile(
    r"password|secret|token|bank|account|ifsc|aadhaar|aadhar|pan(?:_|\s)*(?:number|no)?|passport|photo(?:_|\s)*id",
    re.IGNORECASE,
)


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


def _is_qr_test_sender(sender_phone_number_id):
    sender = WhatsAppPhoneNumber.objects.filter(phone_number_id=sender_phone_number_id).first()
    if not sender:
        return False
    display_digits = "".join(char for char in str(sender.display_phone_number or "") if char.isdigit())
    return display_digits.endswith(QR_TEST_SENDER_SUFFIX)


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
    """Generate raw-JSON QR media for the HR test sender without persisting scan state."""
    if not _has_internal_access(request):
        return HttpResponseForbidden("invalid token")

    body = _json_body(request)
    if body is None:
        return JsonResponse({"ok": False, "error": "invalid json"}, status=400)

    recipient_name = str(body.get("recipient_name") or body.get("guest_name") or "Guest").strip()
    recipient_phone = str(body.get("recipient_phone") or body.get("phone") or "").strip()
    sender_phone_number_id = str(body.get("sender_phone_number_id") or "").strip()
    template_name = str(body.get("template_name") or "").strip()
    if template_name != QR_TEMPLATE_NAME:
        return JsonResponse({"ok": False, "error": f"template_name must be {QR_TEMPLATE_NAME}"}, status=400)
    if not recipient_phone or not sender_phone_number_id:
        return JsonResponse(
            {"ok": False, "error": "recipient_phone and sender_phone_number_id are required"},
            status=400,
        )
    if not _is_qr_test_sender(sender_phone_number_id):
        return JsonResponse(
            {"ok": False, "error": f"Dynamic QR testing is limited to the sender ending in {QR_TEST_SENDER_SUFFIX}"},
            status=403,
        )

    test_id = uuid.uuid4()
    payload = {
        "type": "ank_dynamic_qr_test",
        "test_id": str(test_id),
        "template": QR_TEMPLATE_NAME,
        "generated_at": timezone.now().isoformat(),
        "recipient": {
            "name": recipient_name[:255] or "Guest",
            "phone": recipient_phone[:32],
        },
        "data": _clean_details(body.get("details") or {}),
        "random_code": uuid.uuid4().hex[:12],
    }
    encoded_payload = json.dumps(payload, separators=(",", ":"), ensure_ascii=False, sort_keys=True)

    try:
        access_token, resolved_sender_id = _get_credentials(sender_phone_number_id)
        media_id = _upload_qr_to_meta(_qr_png(encoded_payload), access_token, resolved_sender_id)
    except (WhatsAppError, requests.RequestException) as exc:
        logger.exception("Could not generate QR test media for %s", recipient_phone)
        return JsonResponse({"ok": False, "error": str(exc)}, status=502)

    return JsonResponse(
        {
            "ok": True,
            "media_id": media_id,
            "test_id": str(test_id),
            "qr_payload": payload,
        },
        status=201,
    )
