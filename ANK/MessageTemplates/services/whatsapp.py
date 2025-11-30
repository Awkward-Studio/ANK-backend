import os
import re
import logging

logger = logging.getLogger("whatsapp")

import requests
from typing import Dict, Any, List, Optional


WABA_API_BASE = "https://graph.facebook.com/v21.0"

WABA_TOKEN = os.getenv("WABA_ACCESS_TOKEN", "")
WABA_PHONE_ID = os.getenv("WABA_PHONE_NUMBER_ID", "")
RESUME_TEMPLATE_NAME = os.getenv("WABA_RESUME_TEMPLATE_NAME", "resume_conversation")
RESUME_TEMPLATE_LANG = os.getenv("WABA_RESUME_TEMPLATE_LANG", "en_US")
TRAVEL_DETAIL_TEMPLATE_NAME = "resume_travel_detail"
TRAVEL_DETAIL_TEMPLATE_LANG = "en_US"


class WhatsAppError(Exception):
    pass


def _ensure_creds():
    if not WABA_TOKEN or not WABA_PHONE_ID:
        raise WhatsAppError(
            "WABA credentials are missing. Set WABA_ACCESS_TOKEN and WABA_PHONE_NUMBER_ID."
        )


_digits = re.compile(r"\D+")  # -c add global regex for phone normalization


def _norm_digits(s: str) -> str:
    if not s:
        return ""
    digits = _digits.sub("", s)[-15:]
    if not digits.startswith("+"):
        digits = "+" + digits
    return digits


def _post(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    _ensure_creds()
    url = f"{WABA_API_BASE}/{WABA_PHONE_ID}/{path}"
    logger.warning(f"[WA-POST] URL={url}")
    logger.warning(f"[WA-POST-PAYLOAD] {payload}")

    headers = {
        "Authorization": f"Bearer {WABA_TOKEN}",
        "Content-Type": "application/json",
    }

    r = requests.post(url, headers=headers, json=payload, timeout=15)
    logger.warning(f"[WA-POST-STATUS] {r.status_code}")
    logger.warning(f"[WA-POST-BODY] {r.text}")

    data = r.json() if r.content else {}
    if r.status_code >= 300:
        logger.exception(f"[WA-POST] ERROR {r.status_code}: {data}")
        raise WhatsAppError(f"WABA error {r.status_code}: {data}")
    return data


# def _post(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
#     _ensure_creds()
#     url = f"{WABA_API_BASE}/{WABA_PHONE_ID}/{path}"
#     headers = {
#         "Authorization": f"Bearer {WABA_TOKEN}",
#         "Content-Type": "application/json",
#     }

#     try:
#         r = requests.post(url, headers=headers, json=payload, timeout=15)
#     except Exception as e:
#         raise WhatsAppError(f"Network error sending to WABA: {e}")

#     # Handle non-JSON responses safely
#     try:
#         data = r.json() if r.content else {}
#     except Exception:
#         raise WhatsAppError(
#             f"WABA returned non-JSON response (status={r.status_code}): {r.text[:200]}"
#         )

#     if r.status_code >= 300:
#         raise WhatsAppError(f"WABA error {r.status_code}: {data}")

#     return data


def send_freeform_text(to_wa_id: str, text: str) -> str:
    """
    Sends a free-form WhatsApp text (must be within 24h window).
    Returns provider message id (if any).
    """
    logger.warning(f"[WA-SEND-FREEFORM] TO={to_wa_id} TEXT={text}")
    logger.warning(f"[WA-FREEFORM-PAYLOAD] {text}")
    data = _post(
        "messages",
        {
            "messaging_product": "whatsapp",
            "to": _norm_digits(to_wa_id),
            "type": "text",
            "text": {"body": text or ""},
        },
    )
    logger.warning(f"[WA-FREEFORM-RESPONSE] {data}")
    return (data.get("messages") or [{}])[0].get("id", "")


def send_resume_opener(
    to_wa_id: str, registration_uuid: str, opener_body_param: Optional[str] = None
) -> str:
    """
    Sends the approved 'resume conversation' template with a single quick-reply button.
    The button payload embeds the reg_id: `resume|<reg_uuid>`.
    """
    logger.warning(f"[WA-SEND-RESUME] TO={to_wa_id} REG={registration_uuid}")
    
    components = []
    if opener_body_param:
        components.append(
            {
                "type": "body",
                "parameters": [{"type": "text", "text": opener_body_param}],
            }
        )
    components.append(
        {
            "type": "button",
            "sub_type": "quick_reply",
            "index": 0,
            "parameters": [
                {"type": "payload", "payload": f"resume|{registration_uuid}"}
            ],
        }
    )

    template_payload = {
        "messaging_product": "whatsapp",
        "to": _norm_digits(to_wa_id),
        "type": "template",
        "template": {
            "name": RESUME_TEMPLATE_NAME,
            "language": {"code": RESUME_TEMPLATE_LANG},
            "components": components,
        },
    }
    
    logger.warning(f"[WA-RESUME-PAYLOAD] Template={RESUME_TEMPLATE_NAME}, Components={len(components)}")

    data = _post("messages", template_payload)
    
    msg_id = (data.get("messages") or [{}])[0].get("id", "")
    logger.warning(f"[WA-RESUME-RESPONSE] MessageID={msg_id}")
    
    return msg_id


def within_24h_window(last_inbound) -> bool:
    """
    Checks if last_inbound timestamp is within 24 hours.
    Returns True if last_inbound is within 24 hours, False otherwise.
    """
    if not last_inbound:
        return False
    
    from django.utils import timezone
    from datetime import timedelta
    
    return (timezone.now() - last_inbound) <= timedelta(hours=24)


def send_choice_buttons(
    to_wa_id: str,
    body: str,
    choices: List[Dict[str, str]],
    header: Optional[str] = None,
    footer: Optional[str] = None,
) -> str:
    """
    Send interactive 'button' message with up to 3 choices.
    choices = [{ "id": "tc|step|value", "title": "Air" }, ...]
    """
    logger.warning(f"[WA-SEND-BUTTONS] TO={to_wa_id} TEXT={body}")

    buttons = [
        {
            "type": "reply",
            "reply": {"id": c["id"], "title": (c.get("title") or "")[:20]},
        }
        for c in (choices or [])
    ][:3]

    logger.warning(f"[WA-BUTTONS-LIST] {buttons}")
    if not buttons:

        return send_freeform_text(to_wa_id, body)

    interactive: Dict[str, Any] = {
        "type": "button",
        "body": {"text": body},
        "action": {"buttons": buttons},
    }
    if header:
        interactive["header"] = {"type": "text", "text": header[:60]}
    if footer:
        interactive["footer"] = {"text": footer[:60]}

    logger.warning(f"[WA-BUTTON-PAYLOAD] {interactive}")

    data = _post(
        "messages",
        {
            "messaging_product": "whatsapp",
            "to": _norm_digits(to_wa_id),
            "type": "interactive",
            "interactive": interactive,
        },
    )
    logger.warning(f"[WA-BUTTON-RESPONSE] {data}")

    return (data.get("messages") or [{}])[0].get("id", "")
