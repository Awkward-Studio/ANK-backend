import os
import re
import logging

logger = logging.getLogger("whatsapp")

import requests
from typing import Dict, Any, List, Optional, Tuple


WABA_API_BASE = "https://graph.facebook.com/v21.0"

WABA_TOKEN = os.getenv("WABA_ACCESS_TOKEN", "")
WABA_PHONE_ID = os.getenv("WABA_PHONE_NUMBER_ID", "")
RESUME_TEMPLATE_NAME = os.getenv("WABA_RESUME_TEMPLATE_NAME", "resume_conversation")
RESUME_TEMPLATE_LANG = os.getenv("WABA_RESUME_TEMPLATE_LANG", "en_US")
TRAVEL_DETAIL_TEMPLATE_NAME = "resume_travel_detail"
TRAVEL_DETAIL_TEMPLATE_LANG = "en_US"


class WhatsAppError(Exception):
    pass


def _get_credentials(phone_number_id: Optional[str] = None) -> tuple:
    """
    Get (access_token, phone_number_id) for sending.
    
    Priority:
      1. If phone_number_id provided → lookup in DB
      2. Get default phone number from DB
      3. Fallback to env vars
    
    Returns: (access_token, phone_number_id)
    Raises: WhatsAppError if no credentials found
    """
    try:
        from MessageTemplates.models import WhatsAppPhoneNumber
        
        if phone_number_id:
            # Specific number requested
            phone = WhatsAppPhoneNumber.objects.filter(
                phone_number_id=phone_number_id,
                is_active=True
            ).first()
            if phone:
                token = phone.get_access_token()
                if token:
                    logger.info(f"[WA-CREDS] Using DB credentials for {phone_number_id}")
                    return (token, phone.phone_number_id)
                else:
                    logger.warning(f"[WA-CREDS] No token available for {phone_number_id}")
        else:
            # Get default number
            phone = WhatsAppPhoneNumber.objects.filter(
                is_active=True,
                is_default=True
            ).first()
            if not phone:
                # No default, get any active number
                phone = WhatsAppPhoneNumber.objects.filter(is_active=True).first()
            if phone:
                token = phone.get_access_token()
                if token:
                    logger.info(f"[WA-CREDS] Using default DB number {phone.phone_number_id}")
                    return (token, phone.phone_number_id)
    except Exception as e:
        logger.warning(f"[WA-CREDS] DB lookup failed: {e}, falling back to env")
    
    # Fallback to env vars (backward compatibility)
    if not WABA_TOKEN or not WABA_PHONE_ID:
        raise WhatsAppError("No credentials available (DB or env)")
    
    logger.info("[WA-CREDS] Using env var credentials")
    return (WABA_TOKEN, WABA_PHONE_ID)


_digits = re.compile(r"\D+")  # -c add global regex for phone normalization


def _norm_digits(s: str) -> str:
    if not s:
        return ""
    digits = _digits.sub("", s)[-15:]
    if not digits.startswith("+"):
        digits = "+" + digits
    return digits


def _post(path: str, payload: Dict[str, Any], phone_number_id: Optional[str] = None) -> Dict[str, Any]:
    """
    POST to WhatsApp Cloud API.
    
    Args:
        path: API endpoint (e.g., "messages")
        payload: Request body
        phone_number_id: Optional specific number to send from
        
    Returns:
        Response dict with added '_sender_phone_number_id' key for tracking
    """
    token, sender_id = _get_credentials(phone_number_id)
    
    url = f"{WABA_API_BASE}/{sender_id}/{path}"
    logger.warning(f"[WA-POST] URL={url} SENDER={sender_id}")
    logger.warning(f"[WA-POST-PAYLOAD] {payload}")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    r = requests.post(url, headers=headers, json=payload, timeout=15)
    logger.warning(f"[WA-POST-STATUS] {r.status_code}")
    logger.warning(f"[WA-POST-BODY] {r.text}")

    data = r.json() if r.content else {}
    if r.status_code >= 300:
        logger.exception(f"[WA-POST] ERROR {r.status_code}: {data}")
        raise WhatsAppError(f"WABA error {r.status_code}: {data}")
    
    # Add sender info for tracking
    data['_sender_phone_number_id'] = sender_id
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


def send_freeform_text(to_wa_id: str, text: str, phone_number_id: Optional[str] = None) -> tuple:
    """
    Sends a free-form WhatsApp text (must be within 24h window).
    
    Args:
        to_wa_id: Recipient phone number
        text: Message text
        phone_number_id: Optional specific sender number
        
    Returns:
        Tuple of (message_id, sender_phone_number_id)
    """
    logger.warning(f"[WA-SEND-FREEFORM] TO={to_wa_id} TEXT={text} SENDER={phone_number_id or 'default'}")
    logger.warning(f"[WA-FREEFORM-PAYLOAD] {text}")
    data = _post(
        "messages",
        {
            "messaging_product": "whatsapp",
            "to": _norm_digits(to_wa_id),
            "type": "text",
            "text": {"body": text or ""},
        },
        phone_number_id=phone_number_id
    )
    logger.warning(f"[WA-FREEFORM-RESPONSE] {data}")
    msg_id = (data.get("messages") or [{}])[0].get("id", "")
    sender_id = data.get('_sender_phone_number_id', '')
    return (msg_id, sender_id)


def send_media(
    to_wa_id: str, media_type: str, media_url: str, caption: Optional[str] = None, phone_number_id: Optional[str] = None
) -> tuple:
    """
    Sends a media message (image, video, document, audio) via WhatsApp.
    
    Args:
        to_wa_id: Recipient phone number
        media_type: One of 'image', 'video', 'document', 'audio'
        media_url: URL of the media file
        caption: Optional caption text
        phone_number_id: Optional specific sender number
        
    Returns:
        Tuple of (message_id, sender_phone_number_id)
    """
    logger.warning(
        f"[WA-SEND-MEDIA] TO={to_wa_id} TYPE={media_type} URL={media_url} CAPTION={caption} SENDER={phone_number_id or 'default'}"
    )

    valid_types = {"image", "video", "document", "audio"}
    if media_type not in valid_types:
        raise WhatsAppError(f"Invalid media_type: {media_type}. Must be one of {valid_types}")

    payload_media = {"link": media_url}
    # Audio does not support caption
    if caption and media_type != "audio":
        payload_media["caption"] = caption

    data = _post(
        "messages",
        {
            "messaging_product": "whatsapp",
            "to": _norm_digits(to_wa_id),
            "type": media_type,
            media_type: payload_media,
        },
        phone_number_id=phone_number_id
    )
    logger.warning(f"[WA-MEDIA-RESPONSE] {data}")
    msg_id = (data.get("messages") or [{}])[0].get("id", "")
    sender_id = data.get('_sender_phone_number_id', '')
    return (msg_id, sender_id)


def send_resume_opener(
    to_wa_id: str, registration_uuid: str, opener_body_param: Optional[str] = None, phone_number_id: Optional[str] = None
) -> tuple:
    """
    Sends the approved 'resume conversation' template with a single quick-reply button.
    
    Args:
        to_wa_id: Recipient phone number
        registration_uuid: Registration ID for button payload
        opener_body_param: Optional template body parameter
        phone_number_id: Optional specific sender number
        
    Returns:
        Tuple of (message_id, sender_phone_number_id)
    """
    logger.warning(f"[WA-SEND-RESUME] TO={to_wa_id} REG={registration_uuid} SENDER={phone_number_id or 'default'}")
    
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

    data = _post("messages", template_payload, phone_number_id=phone_number_id)
    
    msg_id = (data.get("messages") or [{}])[0].get("id", "")
    sender_id = data.get('_sender_phone_number_id', '')
    logger.warning(f"[WA-RESUME-RESPONSE] MessageID={msg_id} SENDER={sender_id}")
    
    return (msg_id, sender_id)


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
    phone_number_id: Optional[str] = None
) -> Tuple[str, str]:
    """
    Send interactive 'button' message with up to 3 choices.
    
    Args:
        to_wa_id: Recipient phone number
        body: Message body text
        choices: List of button choices [{ "id": "tc|step|value", "title": "Air" }, ...]
        header: Optional header text
        footer: Optional footer text
        phone_number_id: Optional specific sender number
        
    Returns:
        Tuple of (message_id, sender_phone_number_id)
    """
    logger.warning(f"[WA-SEND-BUTTONS] TO={to_wa_id} TEXT={body} SENDER={phone_number_id or 'default'}")

    buttons = [
        {
            "type": "reply",
            "reply": {"id": c["id"], "title": (c.get("title") or "")[:20]},
        }
        for c in (choices or [])
    ][:3]

    logger.warning(f"[WA-BUTTONS-LIST] {buttons}")
    if not buttons:
        return send_freeform_text(to_wa_id, body, phone_number_id)

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
        phone_number_id=phone_number_id
    )
    logger.warning(f"[WA-BUTTON-RESPONSE] {data}")

    msg_id = (data.get("messages") or [{}])[0].get("id", "")
    sender_id = data.get('_sender_phone_number_id', '')
    return (msg_id, sender_id)


def send_template(
    to_wa_id: str,
    template_name: str,
    language_code: str = "en_US",
    components: List[Dict[str, Any]] = None,
    phone_number_id: Optional[str] = None
) -> Tuple[str, str]:
    """
    Sends a specific template message.
    
    Args:
        to_wa_id: Recipient phone number
        template_name: Template name
        language_code: Language code (default: en_US)
        components: Template components
        phone_number_id: Optional specific sender number
        
    Returns:
        Tuple of (message_id, sender_phone_number_id)
    """
    logger.warning(
        f"[WA-SEND-TEMPLATE] TO={to_wa_id} TEMP={template_name} COMPS={len(components or [])} SENDER={phone_number_id or 'default'}"
    )

    payload = {
        "messaging_product": "whatsapp",
        "to": _norm_digits(to_wa_id),
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": language_code},
            "components": components or [],
        },
    }

    data = _post("messages", payload, phone_number_id=phone_number_id)
    msg_id = (data.get("messages") or [{}])[0].get("id", "")
    sender_id = data.get('_sender_phone_number_id', '')
    return (msg_id, sender_id)

