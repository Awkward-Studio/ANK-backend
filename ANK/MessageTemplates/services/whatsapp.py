import os
import requests
from typing import Dict, Any, Optional
from datetime import timedelta
from django.utils import timezone

WABA_API_BASE = "https://graph.facebook.com/v21.0"

WABA_TOKEN = os.getenv("WABA_ACCESS_TOKEN", "")
WABA_PHONE_ID = os.getenv("WABA_PHONE_NUMBER_ID", "")
RESUME_TEMPLATE_NAME = os.getenv("WABA_RESUME_TEMPLATE_NAME", "resume_conversation")
RESUME_TEMPLATE_LANG = os.getenv("WABA_RESUME_TEMPLATE_LANG", "en_US")


class WhatsAppError(Exception):
    pass


def _ensure_creds():
    if not WABA_TOKEN or not WABA_PHONE_ID:
        raise WhatsAppError(
            "WABA credentials are missing. Set WABA_ACCESS_TOKEN and WABA_PHONE_NUMBER_ID."
        )


def _post(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    _ensure_creds()
    url = f"{WABA_API_BASE}/{WABA_PHONE_ID}/{path}"
    headers = {
        "Authorization": f"Bearer {WABA_TOKEN}",
        "Content-Type": "application/json",
    }
    r = requests.post(url, headers=headers, json=payload, timeout=15)
    data = r.json() if r.content else {}
    if r.status_code >= 300:
        raise WhatsAppError(f"WABA error {r.status_code}: {data}")
    return data


def send_freeform_text(to_wa_id: str, text: str) -> str:
    """
    Sends a free-form WhatsApp text (must be within 24h window).
    Returns provider message id (if any).
    """
    data = _post(
        "messages",
        {
            "messaging_product": "whatsapp",
            "to": to_wa_id,
            "type": "text",
            "text": {"body": text or ""},
        },
    )
    return (data.get("messages") or [{}])[0].get("id", "")


def send_resume_opener(
    to_wa_id: str, registration_uuid: str, opener_body_param: Optional[str] = None
) -> str:
    """
    Sends the approved 'resume conversation' template with a single quick-reply button.
    The button payload embeds the reg_id: `resume|<reg_uuid>`.
    """
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

    data = _post(
        "messages",
        {
            "messaging_product": "whatsapp",
            "to": to_wa_id,
            "type": "template",
            "template": {
                "name": RESUME_TEMPLATE_NAME,
                "language": {"code": RESUME_TEMPLATE_LANG},
                "components": components,
            },
        },
    )
    return (data.get("messages") or [{}])[0].get("id", "")


def within_24h_window(last_inbound: Optional[timezone.datetime]) -> bool:
    """
    Very light window check:
    Returns True if last_inbound is within 24 hours.
    You can later switch this to your own logic (e.g., tracking true inbound timestamps).
    """
    # if not last_inbound:
    #     return False
    # return (timezone.now() - last_inbound) <= timedelta(hours=24)
    return False
