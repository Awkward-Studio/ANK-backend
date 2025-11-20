"""
WhatsApp Travel webhook (forward target from Next.js)

Now fully registration-ID based.
No more wa_id mapping. One phone number can have unlimited registrations.

Incoming payloads ALWAYS include:
{
    "kind": "resume" | "button" | "wake" | "text",
    "wa_id": "<digits>",
    "registration_id": "<uuid>",
    ...
}
"""

import json
import logging
import os
import requests

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone

from Logistics.models.travel_detail_capture_session import TravelCaptureSession
from Events.models.event_registration_model import EventRegistration
from MessageTemplates.services.whatsapp import (
    within_24h_window,
    send_resume_opener,
    send_freeform_text,
    send_choice_buttons,
)

from MessageTemplates.services.travel_info_capture import (
    resume_or_start,
    apply_button_choice,
    handle_inbound_answer,
    send_next_prompt,
    get_fallback_message,
    start_capture_after_opt_in,
)

logger = logging.getLogger("whatsapp")


def _norm_digits(s: str) -> str:
    return "".join(ch for ch in (s or "") if ch.isdigit())[-15:]


def _safe_get_registration(reg_id: str):
    """Return EventRegistration or None. Logs errors safely."""
    if not reg_id:
        # It's common for some payloads (like initial wake) to not have reg_id if coming from generic webhook
        return None

    try:
        return EventRegistration.objects.select_related("guest").get(pk=reg_id)
    except EventRegistration.DoesNotExist:
        logger.error(f"[REG-ERR] Registration {reg_id} not found")
        return None
    except Exception as exc:
        logger.exception(
            f"[REG-EXCEPTION] Unexpected error loading reg {reg_id}: {exc}"
        )
        return None


def _resolve_travel_reg(wa_id: str, event_id: str):
    from Events.models.wa_send_map import WaSendMap

    if not wa_id or not event_id:
        return None

    qs = (
        WaSendMap.objects.filter(
            wa_id=wa_id,
            event_id=event_id,
            template_wamid__isnull=True,
            expires_at__gt=timezone.now(),
        )
        .order_by("-created_at")
        .values_list("event_registration", flat=True)
        .first()
    )

    if not qs:
        return None

    try:
        return EventRegistration.objects.select_related("guest").get(pk=qs)
    except EventRegistration.DoesNotExist:
        return None


@csrf_exempt
@require_http_methods(["POST"])
def whatsapp_travel_webhook(request):
    """Main handler. 100% registration_id based."""
    try:
        body = json.loads(request.body.decode("utf-8"))
        logger.warning(f"[WEBHOOK] INCOMING: {body}")
    except Exception:
        logger.error("[WEBHOOK] Invalid JSON received")
        return JsonResponse({"ok": False, "error": "invalid_json"}, status=400)

    kind = (body.get("kind") or "").strip()
    wa_id = _norm_digits(body.get("wa_id") or "")
    reg_id = body.get("registration_id")
    
    reg = _safe_get_registration(reg_id)

    if not reg:
        reg = _resolve_travel_reg(wa_id, body.get("event_id"))

    if not reg:
        logger.warning(f"[WEBHOOK] No registration resolved (id={reg_id}, wa={wa_id})")
        # Send helpful fallback message instead of silent return
        try:
            wa_phone = wa_id if wa_id else body.get("wa_id", "")
            if wa_phone:
                fallback_msg = get_fallback_message("no_registration")
                send_freeform_text(wa_phone, fallback_msg)
                logger.warning(f"[FALLBACK] Sent no_registration message to {wa_phone}")
        except Exception as exc:
            logger.exception(f"[FALLBACK-ERR] Failed sending fallback for wa_id={wa_id}: {exc}")
        return JsonResponse({"ok": True}, status=200)

    if kind not in {"resume", "button", "wake", "text"}:
        logger.error(f"[WEBHOOK] Invalid kind '{kind}'")
        return JsonResponse({"ok": False, "error": "invalid_kind"}, status=400)

    # Ensure capture session exists
    try:
        sess = reg.travel_capture
    except TravelCaptureSession.DoesNotExist:
        sess = TravelCaptureSession.objects.create(registration=reg)

    # If session already completed AND not a button click, offer update options via text
    if sess.is_complete and kind != "button":
        logger.warning(
            f"[RESUME] Registration={reg.id} session already complete; offering update options."
        )
        try:
            event_name = f" for {reg.event.name}" if reg.event else ""
            message = (
                f"✅ Thank you! We've already received your details{event_name}.\n\n"
                "If you need to update anything:\n"
                "• Reply *rsvp* to change your RSVP status\n"
                "• Reply *travel* to update travel details"
            )
            send_freeform_text(reg.guest.phone, message)
            logger.warning(f"[FALLBACK] Sent update instructions to {reg.guest.phone}")
        except Exception as exc:
            logger.exception(f"[FALLBACK-ERR] Failed sending update instructions to {reg.id}: {exc}")
        return JsonResponse({"ok": True}, status=200)

    # If outside 24h → send auto "resume" template request (RCS)
    if not within_24h_window(reg.responded_on):
        logger.warning(f"[24H] Out-of-window for {reg.id} → sending RESUME_OPENER")
        send_resume_opener(reg.guest.phone, str(reg.id))
        return JsonResponse({"ok": True}, status=200)

    # -------------------------
    #       KIND HANDLING
    # -------------------------

    # === RESUME ===============================================================
    if kind == "resume":
        logger.warning(f"[RESUME] reg={reg.id} restarting/continuing flow")
        try:
            resume_or_start(reg)
        except Exception as exc:
            logger.exception(f"[RESUME-ERR] Failed resume for {reg.id}: {exc}")
        return JsonResponse({"ok": True}, status=200)

    # === BUTTON ===============================================================
    if kind == "button":
        # We support:
        #  1) New: explicit {"step": "...", "value": "..."}
        #  2) Standard: {"button_id": "tc|step|value"}
        step = (body.get("step") or "").strip()
        value = (body.get("value") or "").strip()

        if not (step and value):
            btn_id = (body.get("button_id") or "").strip()
            
            # DIAGNOSTIC: Send test message to confirm button click received
            logger.warning(f"[BUTTON-DEBUG] Received button_id: {btn_id!r}")
            
            try:
                parts = btn_id.split("|", 2)
                logger.warning(f"[BUTTON-DEBUG] Split into parts: {parts}")
                
                # Check for "tc" prefix (standard Travel Capture format)
                if len(parts) >= 2 and parts[0] == "tc":
                    step = parts[1]
                    value = parts[2] if len(parts) > 2 else ""
                
                # --- BACKWARD COMPATIBILITY for legacy buttons ---
                # Handle "update" buttons (e.g., "update|rsvp|uuid")
                elif len(parts) >= 2 and parts[0] == "update":
                    action = parts[1]
                    # Map legacy action to new step name
                    if action == "rsvp":
                        step = "update_rsvp"
                    elif action == "travel":
                        step = "update_travel"
                    value = parts[2] if len(parts) > 2 else ""
                    logger.warning(f"[LEGACY-BUTTON] Mapped update|{action} to step={step}")

                # Handle "rsvp" buttons (e.g., "rsvp|yes|uuid")
                elif len(parts) >= 2 and parts[0] == "rsvp":
                    status = parts[1]
                    # Map legacy status to new step name
                    if status in ["yes", "no", "maybe"]:
                        step = f"rsvp_{status}"
                    value = parts[2] if len(parts) > 2 else ""
                    logger.warning(f"[LEGACY-BUTTON] Mapped rsvp|{status} to step={step}")
            except Exception:
                logger.error(f"[BUTTON-ERR] Malformed button_id: {btn_id}")

        if step and value:
            try:
                logger.warning(
                    f"[WEBHOOK-BUTTON] step={step!r} value={value!r} reg={reg.id}"
                )
                # Delegate EVERYTHING to the orchestrator
                apply_button_choice(reg, step, value)
            except Exception as exc:
                logger.exception(f"[BUTTON-EXCEPTION] Failed for reg={reg.id}: {exc}")
        else:
            logger.error(f"[BUTTON] Could not resolve step/value from payload: {body}")

        return JsonResponse({"ok": True}, status=200)

    # === WAKE ================================================================
    if kind == "wake":
        logger.warning(f"[WAKE] Registration={reg.id} WAKE triggered")
        try:
            resume_or_start(reg)
        except Exception as exc:
            logger.exception(f"[WAKE-ERR] Failed resume for {reg.id}: {exc}")
        return JsonResponse({"ok": True}, status=200)

    # === TEXT ================================================================
    if kind == "text":
        text = (body.get("text") or "").strip()
        if not text:
            logger.warning(f"[TEXT] Empty text for reg={reg.id}")
            return JsonResponse({"ok": True}, status=200)

        # Check if we're awaiting guest count for RSVP
        try:
            # 0. Check for explicit commands
            text_lower = text.lower()
            
            # "update" / "menu" - shows instructions
            if text_lower in ["update", "change", "modify", "menu"]:
                logger.warning(f"[TEXT-TRIGGER] User asked for update menu: '{text}'")
                send_freeform_text(
                    reg.guest.phone,
                    "To make changes, please reply with:\n\n"
                    "• *rsvp* - to update your RSVP status\n"
                    "• *travel* - to update your travel details"
                )
                return JsonResponse({"ok": True}, status=200)
            
            # "rsvp" - triggers RSVP flow
            if text_lower in ["rsvp", "update rsvp", "change rsvp"]:
                logger.warning(f"[TEXT-TRIGGER] User triggered RSVP update: '{text}'")
                event_name = reg.event.name if reg.event else "the event"
                send_choice_buttons(
                    reg.guest.phone,
                    f"Will you be attending {event_name}? 🎉",
                    [
                        {"id": f"tc|rsvp_yes|{reg.id}", "title": "✅ Yes"},
                        {"id": f"tc|rsvp_no|{reg.id}", "title": "❌ No"},
                        {"id": f"tc|rsvp_maybe|{reg.id}", "title": "🤔 Maybe"},
                    ]
                )
                return JsonResponse({"ok": True}, status=200)
            
            # "travel" - triggers Travel flow restart
            if text_lower in ["travel", "update travel", "change travel"]:
                logger.warning(f"[TEXT-TRIGGER] User triggered Travel update: '{text}'")
                start_capture_after_opt_in(reg, restart=True)
                return JsonResponse({"ok": True}, status=200)

            sess = reg.travel_capture
            if sess.state and sess.state.get("awaiting_guest_count"):
                logger.warning(f"[RSVP-GUEST-COUNT] Processing guest count for {reg.id}: '{text}'")
                
                # Parse guest count
                try:
                    count = int(text)
                    if count < 1 or count > 50:
                        raise ValueError("Out of range")
                    
                    # Update registration
                    reg.estimated_pax = count
                    reg.save(update_fields=["estimated_pax"])
                    
                    # Clear flag
                    sess.state.pop("awaiting_guest_count", None)
                    sess.save(update_fields=["state"])
                    
                    # Send confirmation
                    event_name = reg.event.name if reg.event else "the event"
                    send_freeform_text(
                        reg.guest.phone,
                        f"✅ Perfect! Your RSVP has been updated:\n"
                        f"• Event: {event_name}\n"
                        f"• Status: Confirmed\n"
                        f"• Total Guests: {count}\n\n"
                        "We're looking forward to seeing you! 🎉"
                    )
                    logger.warning(f"[RSVP-GUEST-COUNT] Successfully updated guest count to {count} for {reg.id}")
                    return JsonResponse({"ok": True}, status=200)
                    
                except ValueError:
                    # Invalid number
                    send_freeform_text(
                        reg.guest.phone,
                        "Please reply with a valid number of guests between 1 and 50 (e.g., 2, 3, 4)"
                    )
                    logger.warning(f"[RSVP-GUEST-COUNT] Invalid count '{text}' for {reg.id}")
                    return JsonResponse({"ok": True}, status=200)
        except Exception as exc:
            logger.exception(f"[RSVP-GUEST-COUNT-ERR] Error processing guest count: {exc}")

        try:
            reply_text, done = handle_inbound_answer(reg, text)
        except Exception as exc:
            logger.exception(f"[TEXT-ERR] Unable to process text for {reg.id}: {exc}")
            return JsonResponse({"ok": True}, status=200)

        # Always send the textual reply (either next prompt or validation error)
        if reply_text:
            try:
                send_freeform_text(reg.guest.phone, reply_text)
            except Exception as exc:
                logger.exception(
                    f"[TEXT-SEND-ERR] Failed sending message to {reg.id}: {exc}"
                )

        return JsonResponse({"ok": True}, status=200)

    # Should never reach here
    return JsonResponse({"ok": True}, status=200)
