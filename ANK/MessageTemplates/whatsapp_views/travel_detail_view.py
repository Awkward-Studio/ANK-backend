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
from Events.services.message_logger import MessageLogger

logger = logging.getLogger("whatsapp")


def _norm_digits(s: str) -> str:
    return "".join(ch for ch in (s or "") if ch.isdigit())[-15:]



# _update_responded_on REMOVED - replaced by MessageLogger


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


def _send_post_rsvp_options(reg: EventRegistration):
    """Send options to user who completed RSVP but hasn't started travel."""
    event_name = reg.event.name if reg.event else "the event"
    
    message = (
        f"Thank you for confirming your RSVP for {event_name}! ✅\n\n"
        "What would you like to do next?"
    )
    
    buttons = [
        {
            "id": f"tc|start_travel|{reg.id}",
            "title": "Add Travel Details"
        },
        {
            "id": f"tc|update_rsvp_menu|{reg.id}",
            "title": "Update RSVP"
        },
        {
            "id": f"tc|remind_later|{reg.id}",
            "title": "⏰ Remind Me Later"
        }
    ]
    
    MessageLogger.send_buttons(reg, message, buttons, "rsvp")
    logger.info(f"[POST-RSVP] Sent options to registration {reg.id}")


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

    # Fetch capture session (don't auto-create)
    sess = None
    try:
        sess = reg.travel_capture
    except TravelCaptureSession.DoesNotExist:
        pass  # Don't auto-create; handle below based on state

    # If outside 24h → send auto "resume" template request (RCS)
    # Check this early for all message types except resume
    if kind != "resume" and not within_24h_window(reg.responded_on):
        logger.warning(f"[24H] Out-of-window for {reg.id} → sending RESUME_OPENER")
        MessageLogger.send_resume_template(reg)
        return JsonResponse({"ok": True}, status=200)

    # -------------------------
    #       KIND HANDLING
    # -------------------------

    # === RESUME ===============================================================
    if kind == "resume":
        logger.warning(f"[RESUME] reg={reg.id} restarting/continuing flow")
        # Update responded_on when guest resumes conversation
        MessageLogger.log_inbound(reg, "Resume / Continue", "system", wa_id, body)
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
        btn_id = ""  # Initialize before conditional

        if not (step and value):
            btn_id = (body.get("button_id") or "").strip()
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
                # Log inbound button click
                MessageLogger.log_inbound(reg, f"Button: {step}={value}", "button", btn_id or wa_id, body)
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
        # Update responded_on when guest initiates conversation
        MessageLogger.log_inbound(reg, "Wake / Init", "system", wa_id, body)
        try:
            # If session exists and is complete, send update instructions
            if sess and sess.is_complete:
                logger.warning(f"[WAKE] Registration={reg.id} session complete; sending instructions")
                event_name = f" for {reg.event.name}" if reg.event else ""
                message = (
                    f"✅ Thank you! We've already received your details{event_name}.\n\n"
                    "If you need to update anything:\n"
                    "• Reply *rsvp* to change your RSVP status\n"
                    "• Reply *travel* to update travel details"
                )
                MessageLogger.send_text(reg, message, "system")
                return JsonResponse({"ok": True}, status=200)

            # If session exists but incomplete, resume
            if sess:
                resume_or_start(reg)
            else:
                # No session - send post-RSVP options
                _send_post_rsvp_options(reg)
        except Exception as exc:
            logger.exception(f"[WAKE-ERR] Failed resume for {reg.id}: {exc}")
        return JsonResponse({"ok": True}, status=200)

    # === TEXT ================================================================
    if kind == "text":
        text = (body.get("text") or "").strip()
        if not text:
            logger.warning(f"[TEXT] Empty text for reg={reg.id}")
            return JsonResponse({"ok": True}, status=200)
        
        # Update responded_on when guest sends a text message
        MessageLogger.log_inbound(reg, text, "content", wa_id, body)

        # Check for explicit commands FIRST (before any state checks)
        text_lower = text.lower()
        
        # "update" / "menu" - shows menu buttons
        if any(x in text_lower for x in ["update", "change", "modify", "menu"]):
            logger.warning(f"[TEXT-TRIGGER] User asked for update menu: '{text}'")
            try:
                MessageLogger.send_buttons(
                    reg,
                    "What would you like to do? 📋",
                    [
                        {"id": f"tc|start_travel|{reg.id}", "title": "✈️ Update Travel"},
                        {"id": f"tc|update_rsvp_menu|{reg.id}", "title": "🔄 Update RSVP"},
                        {"id": f"tc|remind_later|{reg.id}", "title": "⏰ Remind Later"},
                    ],
                    "system"
                )
            except Exception as exc:
                logger.exception(f"[TEXT-ERR] Failed sending update menu: {exc}")
            return JsonResponse({"ok": True}, status=200)
        
        # "rsvp" - triggers RSVP flow
        if "rsvp" in text_lower:
            logger.warning(f"[TEXT-TRIGGER] User triggered RSVP update: '{text}'")
            try:
                event_name = reg.event.name if reg.event else "the event"
                MessageLogger.send_buttons(
                    reg,
                    f"Will you be attending {event_name}? 🎉",
                    [
                        {"id": f"tc|rsvp_yes|{reg.id}", "title": "✅ Yes"},
                        {"id": f"tc|rsvp_no|{reg.id}", "title": "❌ No"},
                        {"id": f"tc|rsvp_maybe|{reg.id}", "title": "🤔 Maybe"},
                    ],
                    "rsvp"
                )
            except Exception as exc:
                logger.exception(f"[TEXT-ERR] Failed sending RSVP buttons: {exc}")
            return JsonResponse({"ok": True}, status=200)
        
        # "travel" - triggers Travel flow restart
        if "travel" in text_lower:
            logger.warning(f"[TEXT-TRIGGER] User triggered Travel update: '{text}'")
            try:
                start_capture_after_opt_in(reg, restart=True)
            except Exception as exc:
                logger.exception(f"[TEXT-ERR] Failed starting travel flow: {exc}")
            return JsonResponse({"ok": True}, status=200)
        
        # Greetings or "help" / "hi" / "hello" - send a friendly menu
        if any(x in text_lower for x in ["help", "hi", "hello", "hey", "namaste", "hii", "hiii"]):
            logger.warning(f"[TEXT-TRIGGER] User sent greeting/help: '{text}'")
            try:
                if sess and not sess.is_complete:
                    # Active session - send buttons to continue or change
                    MessageLogger.send_buttons(
                        reg,
                        "👋 Hi there! You're currently providing your travel details.\n\n"
                        "What would you like to do?",
                        [
                            {"id": f"tc|continue_flow|{reg.id}", "title": "▶️ Continue"},
                            {"id": f"tc|start_travel|{reg.id}", "title": "🔄 Restart Travel"},
                            {"id": f"tc|update_rsvp_menu|{reg.id}", "title": "📝 Update RSVP"},
                        ],
                        "system"
                    )
                else:
                    _send_post_rsvp_options(reg)
            except Exception as exc:
                logger.exception(f"[TEXT-ERR] Failed sending greeting response: {exc}")
            return JsonResponse({"ok": True}, status=200)

        # If no session exists and not a command, do NOT send post-RSVP options automatically.
        # This prevents "travel detail" loops when users reply to bulk messages.
        if not sess:
            # GLOBAL MENU FALLBACK
            # If the user sends a message and is NOT in a specific travel flow,
            # we check if they have any active registrations and send them a menu.
            
            wa_digits = "".join(c for c in wa_id if c.isdigit())[-15:]
            
            # Find active registrations (future events or recent past)
            # You might want to filter by Event.start_date >= today
            active_regs = EventRegistration.objects.filter(
                guest__phone__endswith=wa_digits
            ).select_related('event').order_by('-event__start_date')[:3]

            if active_regs:
                msg_body = "👋 Welcome back! Here are your events:\n\n"
                rows = []
                for reg in active_regs:
                    evt_name = reg.event.name
                    status = reg.rsvp_status or "Pending"
                    # We can't easily make these clickable list items without a template,
                    # so we'll just list them as text for now, or send a generic "My Events" button.
                    msg_body += f"• *{evt_name}* (RSVP: {status})\n"
                
                msg_body += "\nReply with specific commands or wait for an admin to reply."
                
                # We can also send a helper button if desired, but simple text is safe.
                from Events.services.message_logger import MessageLogger
                
                # Use the first registration as a proxy for sending the message
                # (MessageLogger requires a registration to link the log to)
                proxy_reg = active_regs[0]
                
                MessageLogger.send_text(
                    event_registration=proxy_reg,
                    content=msg_body,
                    message_type="bot_reply"
                )
                logger.info(f"[TEXT] Sent Global Menu to {wa_id} (found {len(active_regs)} events)")
                return JsonResponse({"ok": True, "menu_sent": True})

            else:
                # Unknown user? Or no active events.
                # Send a generic "Contact us" message.
                msg_body = (
                    "👋 Hello! We couldn't find any active events linked to this number.\n\n"
                    "If you believe this is a mistake, please contact the event admin directly."
                )
                try:
                    from MessageTemplates.services.whatsapp import send_freeform_text
                    send_freeform_text(wa_id, msg_body)
                    logger.info(f"[TEXT] Sent Unknown User generic reply to {wa_id}")
                except Exception as e:
                    logger.error(f"[TEXT] Failed to send Unknown User reply: {e}")

            logger.warning(f"[TEXT] No session & no active events for {wa_id}, logging only.")
            return JsonResponse({"ok": True}, status=200)

        # If session is complete (and it wasn't a command), send instructions
        if sess.is_complete:
            logger.warning(f"[TEXT] Registration={reg.id} session complete; sending instructions for '{text}'")
            try:
                event_name = f" for {reg.event.name}" if reg.event else ""
                MessageLogger.send_buttons(
                    reg,
                    f"✅ Thank you! We've already received your details{event_name}.\n\n"
                    "What would you like to do?",
                    [
                        {"id": f"tc|start_travel|{reg.id}", "title": "✈️ Update Travel"},
                        {"id": f"tc|update_rsvp_menu|{reg.id}", "title": "🔄 Update RSVP"},
                    ],
                    "system"
                )
            except Exception as exc:
                logger.exception(f"[TEXT-ERR] Failed sending instructions: {exc}")
            return JsonResponse({"ok": True}, status=200)

        # Process text as travel answer only if session exists and incomplete
        try:
            reply_text, done = handle_inbound_answer(reg, text)
        except Exception as exc:
            logger.exception(f"[TEXT-ERR] Unable to process text for {reg.id}: {exc}")
            return JsonResponse({"ok": True}, status=200)

        # Always send the textual reply (either next prompt or validation error)
        if reply_text:
            try:
                MessageLogger.send_text(reg, reply_text, "travel")
            except Exception as exc:
                logger.exception(
                    f"[TEXT-SEND-ERR] Failed sending message to {reg.id}: {exc}"
                )

        return JsonResponse({"ok": True}, status=200)

    # Should never reach here
    return JsonResponse({"ok": True}, status=200)
