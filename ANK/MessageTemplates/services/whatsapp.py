import requests
import logging
from django.conf import settings
from django.utils.timezone import now, timedelta

logger = logging.getLogger(__name__)

WABA_API_BASE = "https://graph.facebook.com/v21.0"


def within_24h_window(last_incoming_ts):
    """
    Check if we can send a free-form message (within 24h of last inbound message).
    last_incoming_ts: datetime of last inbound message from guest (stored on EventRegistration?).
    """
    if not last_incoming_ts:
        return False
    return (now() - last_incoming_ts) <= timedelta(hours=24)


def send_freeform_message(phone_number: str, text: str) -> dict:
    """
    Sends a free-form text message (allowed only inside 24h).
    """
    url = f"{WABA_API_BASE}/{settings.WABA_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {settings.WABA_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "text",
        "text": {"body": text},
    }
    r = requests.post(url, headers=headers, json=payload, timeout=10)
    r.raise_for_status()
    return r.json()


def send_continue_template(phone_number: str, registration_id: str) -> dict:
    """
    Sends an approved template with a button to re-open conversation.
    """
    url = f"{WABA_API_BASE}/{settings.WABA_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {settings.WABA_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "template",
        "template": {
            "name": settings.WABA_TEMPLATE_NAME,  # approved template
            "language": {"code": settings.WABA_TEMPLATE_LANG},
            "components": [
                {
                    "type": "button",
                    "sub_type": "quick_reply",
                    "index": 0,
                    "parameters": [
                        {"type": "payload", "payload": f"resume|{registration_id}"}
                    ],
                }
            ],
        },
    }
    r = requests.post(url, headers=headers, json=payload, timeout=10)
    r.raise_for_status()
    return r.json()
