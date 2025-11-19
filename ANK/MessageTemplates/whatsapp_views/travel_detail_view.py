"""
WhatsApp Travel webhook (forward target from Next.js)

This endpoint is called by your single Next.js webhook for **travel** events only.
It delegates all conversation logic to the orchestrator (travel_info_capture.py).

Accepted POST payloads from Next.js:
  {
    "kind": "resume" | "button" | "wake" | "text",
    "wa_id": "<digits-only>",                    # sender phone (normalized)
    "payload": "resume|<reg_uuid>",              # when kind == "resume"
    "button_id": "tc|<step>|<value>",            # when kind == "button"
    "text": "<free text>",                       # when kind == "text"
    "template_wamid": "<optional wamid>"
  }
"""

import logging

logger = logging.getLogger("travel_debug")


import json
from datetime import datetime

from django.http import JsonResponse
from django.utils import timezone as dj_tz
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from Events.models.event_registration_model import EventRegistration
from Events.models.wa_send_map import WaSendMap
from MessageTemplates.services.whatsapp import (
    within_24h_window,
    send_resume_opener,
    send_freeform_text,
)
from MessageTemplates.services.travel_info_capture import (
    resume_or_start,
    apply_button_choice,
    handle_inbound_answer,
    send_next_prompt,
)


def _norm_digits(s: str) -> str:
    if not s:
        return ""
    digits = "".join(ch for ch in s if ch.isdigit())
    if len(digits) == 12 and digits.startswith("91"):
        return f"+{digits}"
    if len(digits) == 10:
        return f"+91{digits}"
    return f"+{digits}"


def _resolve_reg_by_wa(wa_id: str):
    """Resolve the most recent registration mapped to this wa_id."""
    print("DEBUG WA_ID =", wa_id)
    print("DEBUG DB =", list(WaSendMap.objects.values_list("wa_id", flat=True)[:20]))

    rid = (
        WaSendMap.objects.filter(wa_id=wa_id)
        .order_by("-created_at")
        .values_list("event_registration", flat=True)
        .first()
    )
    if not rid:
        return None
    try:
        return EventRegistration.objects.select_related("guest").get(pk=rid)
    except EventRegistration.DoesNotExist:
        return None


@csrf_exempt
@require_http_methods(["POST"])
def whatsapp_travel_webhook(request):
    logger = logging.getLogger("travel_webhook")

    # -------- SAFE JSON LOAD --------
    print("A -------- webhook reached BEFORE BODY LOG")

    print("BODY_RAW=", request.body)
    logger.warning("WEBHOOK HIT")

    try:
        logger.warning(request.body)
        print("B -------- BODY LOG OK")
    except Exception as e:
        print("LOGGER CRASHED:", e)
    try:
        body = json.loads(request.body.decode("utf-8"))
    except Exception:
        logger.exception("INVALID JSON RECEIVED")
        return JsonResponse({"ok": True}, status=200)

    logger.warning("WEBHOOK HIT")
    logger.warning(str(request.body))

    kind = (body.get("kind") or "").strip()
    wa_id = _norm_digits(body.get("wa_id") or "")

    if not wa_id or kind not in {"resume", "button", "wake", "text"}:
        return JsonResponse({"ok": True}, status=200)

    # ------ RESUME case ------
    if kind == "resume":
        try:
            payload = body.get("payload") or ""
            reg_id = payload.split("|", 1)[1]
            reg = EventRegistration.objects.get(pk=reg_id)
            resume_or_start(reg)
        except Exception:
            logger.exception("RESUME FAILED")
        return JsonResponse({"ok": True}, status=200)

    # ------ RESOLVE REGISTRATION ------
    try:
        reg = _resolve_reg_by_wa(wa_id)
    except Exception:
        logger.exception("WA RESOLUTION FAILED")
        return JsonResponse({"ok": True}, status=200)

    if not reg:
        return JsonResponse({"ok": True}, status=200)

    # update timestamp
    reg.responded_on = dj_tz.now()
    reg.save(update_fields=["responded_on"])

    # ------ BUTTON INTERACTION ------
    if kind == "button":
        try:
            button_id = body.get("button_id") or ""
            parts = button_id.split("|", 2)
            if len(parts) == 3 and parts[0] == "tc":
                step, value = parts[1], parts[2]
                apply_button_choice(reg, step, value)
        except Exception:
            logger.exception("BUTTON HANDLING FAILED")

        return JsonResponse({"ok": True}, status=200)

    # ------ WAKE FLOW ------
    if kind == "wake":
        try:
            resume_or_start(reg)
        except Exception:
            logger.exception("WAKE FAILED")
        return JsonResponse({"ok": True}, status=200)

    # ------ TEXT FLOW ------
    if kind == "text":
        text = (body.get("text") or "").strip()

        try:
            reply_text, done = handle_inbound_answer(reg, text)
        except Exception:
            logger.exception("TEXT PARSE FAILED")
            reply_text = None
            done = False

        try:
            if done:
                if reply_text:
                    send_freeform_text(reg.guest.phone, reply_text)
            elif reply_text:
                send_freeform_text(reg.guest.phone, reply_text)
            else:
                send_next_prompt(reg)
        except Exception:
            logger.exception("TEXT SEND FAILED")

        return JsonResponse({"ok": True}, status=200)

    # fallback
    return JsonResponse({"ok": True}, status=200)


# """
# WhatsApp Travel webhook (forward target from Next.js)

# This endpoint is called by your single Next.js webhook for **travel** events only.
# It delegates all conversation logic to the orchestrator (travel_convo.py).

# Accepted POST payloads from Next.js:
#   {
#     "kind": "resume" | "button" | "wake" | "text",
#     "wa_id": "<digits-only>",                    # sender phone (normalized)
#     "payload": "resume|<reg_uuid>",              # when kind == "resume"
#     "button_id": "tc|<step>|<value>",            # when kind == "button"
#     "text": "<free text>",                       # when kind == "text"
#     "template_wamid": "<optional wamid>"
#   }

# This view:
# - Resolves the EventRegistration using WaSendMap (latest by wa_id).
# - Uses orchestrator functions:
#     • resume_or_start(reg)
#     • apply_button_choice(reg, step, value)
#     • handle_inbound_answer(reg, text) -> (reply, done)
#     • send_next_prompt(reg)
# - Re-opens session via `request_travel_details` template if outside 24h window.
# """

# import json
# from django.http import JsonResponse
# from django.views.decorators.csrf import csrf_exempt
# from django.views.decorators.http import require_http_methods

# from Events.models.event_registration_model import EventRegistration
# from Events.models.wa_send_map import WaSendMap
# from MessageTemplates.services.whatsapp import (
#     within_24h_window,
#     send_resume_opener,
#     send_freeform_text,
# )
# from MessageTemplates.services.travel_info_capture import (
#     resume_or_start,
#     apply_button_choice,
#     handle_inbound_answer,
#     send_next_prompt,
# )


# def _norm_digits(s: str) -> str:
#     """Keep last 10–15 digits for resilience."""
#     return "".join(ch for ch in (s or "") if ch.isdigit())[-15:]


# def _resolve_reg_by_wa(wa_id: str):
#     """Resolve the most recent registration mapped to this wa_id."""
#     rid = (
#         WaSendMap.objects.filter(wa_id=wa_id)
#         .order_by("-created_at")
#         .values_list("event_registration", flat=True)
#         .first()
#     )
#     if not rid:
#         return None
#     try:
#         return EventRegistration.objects.select_related("guest").get(pk=rid)
#     except EventRegistration.DoesNotExist:
#         return None


# @csrf_exempt
# @require_http_methods(["POST"])
# def whatsapp_travel_webhook(request):
#     try:
#         body = json.loads(request.body.decode("utf-8"))
#     except Exception:
#         return JsonResponse({"ok": False, "error": "invalid_json"}, status=400)

#     kind = (body.get("kind") or "").strip()
#     wa_id = _norm_digits(body.get("wa_id") or "")

#     if not wa_id or kind not in {"resume", "button", "wake", "text"}:
#         return JsonResponse({"ok": False, "error": "bad_request"}, status=400)

#     # --- kind: resume (payload = "resume|<reg_uuid>")
#     if kind == "resume":
#         p = body.get("payload") or ""
#         reg_id = p.split("|", 1)[1] if p.startswith("resume|") else ""
#         if not reg_id:
#             return JsonResponse(
#                 {"ok": False, "error": "bad_resume_payload"}, status=400
#             )
#         try:
#             reg = EventRegistration.objects.select_related("guest").get(pk=reg_id)
#         except EventRegistration.DoesNotExist:
#             return JsonResponse({"ok": True}, status=200)
#         # Resume from saved step (or start if new) and immediately prompt
#         resume_or_start(reg)
#         return JsonResponse({"ok": True}, status=200)

#     # For the rest, resolve by wa_id mapping
#     reg = _resolve_reg_by_wa(wa_id)
#     if not reg:
#         return JsonResponse({"ok": True}, status=200)

#     # Out-of-window? Send the resume template *before* doing anything else
#     if not within_24h_window(reg.responded_on):
#         send_resume_opener(reg.guest.phone, str(reg.id))
#         return JsonResponse({"ok": True}, status=200)

#     # --- kind: button (interactive button pressed in-session)
#     if kind == "button":
#         btn_id = (body.get("button_id") or "").strip()  # e.g., "tc|arrival|self"
#         parts = btn_id.split("|", 2)
#         if len(parts) == 3 and parts[0] == "tc":
#             step, value = parts[1], parts[2]
#             apply_button_choice(
#                 reg, step, value
#             )  # applies + auto-advances via orchestrator
#         return JsonResponse({"ok": True}, status=200)

#     # --- kind: wake (guest typed "travel"/"resume"/"continue")
#     if kind == "wake":
#         # Resume and send the next appropriate prompt (buttons for choice, text otherwise)
#         resume_or_start(reg)
#         return JsonResponse({"ok": True}, status=200)

#     # --- kind: text (free-text reply for non-choice steps)
#     if kind == "text":
#         text = (body.get("text") or "").strip()
#         if not text:
#             return JsonResponse({"ok": True}, status=200)

#         reply_text, done, is_button_step = handle_inbound_answer(reg, text)

#         if is_button_step:
#             # next question is a button step → orchestrator must send it
#             send_next_prompt(reg)
#         else:
#             # plain prompt → text only
#             if reply_text:
#                 send_freeform_text(reg.guest.phone, reply_text)

#         return JsonResponse({"ok": True}, status=200)
