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

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from Logistics.models.travel_detail_capture_session import TravelCaptureSession
from Events.models.event_registration_model import EventRegistration
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

logger = logging.getLogger("whatsapp")


def _norm_digits(s: str) -> str:
    return "".join(ch for ch in (s or "") if ch.isdigit())[-15:]


def _safe_get_registration(reg_id: str):
    """Return EventRegistration or None. Logs errors safely."""
    if not reg_id:
        logger.error("[REG-ERR] No registration_id provided in webhook payload")
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
    from django.utils import timezone

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

        logger.warning(f"[WEBHOOK] No registration resolved (id={reg_id}, wa={wa_id})")
        # Send helpful fallback message instead of silent return
        from MessageTemplates.services.travel_info_capture import get_fallback_message
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

    # If session already completed AND not a button click, offer update options
    # (button clicks need to be processed even for completed sessions)
    if sess.is_complete and kind != "button":
        logger.warning(
            f"[RESUME] Registration={reg.id} session already complete; offering update options."
        )
        # Send message with update buttons
        from MessageTemplates.services.whatsapp import send_choice_buttons
        try:
            event_name = f" for {reg.event.name}" if reg.event else ""
            message = (
                f"✅ Thank you! We've already received your details{event_name}.\n\n"
                "What would you like to update?"
            )
            send_choice_buttons(
                reg.guest.phone,
                message,
                [
                    {"id": f"update|rsvp|{reg.id}", "title": "📝 Update RSVP"},
                    {"id": f"update|travel|{reg.id}", "title": "✈️ Update Travel Details"},
                ]
            )
            logger.warning(f"[FALLBACK] Sent update options to {reg.guest.phone}")
        except Exception as exc:
            logger.exception(f"[FALLBACK-ERR] Failed sending update options to {reg.id}: {exc}")
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
    # if kind == "button":
    #     btn_id = (body.get("button_id") or "").strip()
    #     step, value = None, None

    #     try:
    #         parts = btn_id.split("|", 2)
    #         if len(parts) == 3 and parts[0] == "tc":
    #             step, value = parts[1], parts[2]
    #     except Exception:
    #         logger.error(f"[BUTTON-ERR] Malformed button_id: {btn_id}")

    #     if step and value:
    #         try:
    #             apply_button_choice(reg, step, value)
    #         except Exception as exc:
    #             logger.exception(f"[BUTTON-EXCEPTION] Failed for reg={reg.id}: {exc}")

    #     return JsonResponse({"ok": True}, status=200)
    if kind == "button":
        # We now support multiple formats:
        #  1) New: explicit {"step": "...", "value": "..."}
        #  2) Old: {"button_id": "tc|step|value"}
        #  3) Update: {"button_id": "update|action|reg_id"}
        step = (body.get("step") or "").strip()
        value = (body.get("value") or "").strip()

        if not (step and value):
            btn_id = (body.get("button_id") or "").strip()
            
            # DIAGNOSTIC: Send test message to confirm button click received
            logger.warning(f"[BUTTON-DEBUG] Received button_id: {btn_id!r}")
            
            try:
                parts = btn_id.split("|", 2)
                logger.warning(f"[BUTTON-DEBUG] Split into parts: {parts}")
                
                # Handle "update" buttons (e.g., "update|rsvp|uuid" or "update|travel|uuid")
                if len(parts) >= 2 and parts[0] == "update":
                    action = parts[1] if len(parts) > 1 else "unknown"  # "rsvp" or "travel"
                    reg_id_from_btn = parts[2] if len(parts) > 2 else "missing"
                    
                    logger.warning(f"[WEBHOOK-UPDATE-BUTTON] action={action!r} reg={reg.id}")
                    
                    # DIAGNOSTIC: Send WhatsApp message to confirm button was received
                    try:
                        send_freeform_text(
                            reg.guest.phone,
                            f"🔧 DEBUG: Update button clicked! Action={action}, Button ID={btn_id}"
                        )
                    except:
                        pass
                    
                    if action == "travel":
                        # Restart travel capture flow
                        from MessageTemplates.services.travel_info_capture import start_capture_after_opt_in
                        try:
                            start_capture_after_opt_in(reg, restart=True)
                            logger.warning(f"[UPDATE-TRAVEL] Restarted travel capture for {reg.id}")
                        except Exception as exc:
                            logger.exception(f"[UPDATE-TRAVEL-ERR] Failed for {reg.id}: {exc}")
                    
                    elif action == "rsvp":
                        # Send RSVP status buttons
                        try:
                            event_name = reg.event.name if reg.event else "the event"
                            send_choice_buttons(
                                reg.guest.phone,
                                f"Will you be attending {event_name}? 🎉",
                                [
                                    {"id": f"rsvp|yes|{reg.id}", "title": "✅ Yes"},
                                    {"id": f"rsvp|no|{reg.id}", "title": "❌ No"},
                                    {"id": f"rsvp|maybe|{reg.id}", "title": "🤔 Maybe"},
                                ]
                            )
                            logger.warning(f"[UPDATE-RSVP] Sent RSVP status buttons to {reg.id}")
                        except Exception as exc:
                            logger.exception(f"[UPDATE-RSVP-ERR] Failed for {reg.id}: {exc}")
                    
                    return JsonResponse({"ok": True}, status=200)
                
                # Handle "rsvp" buttons (e.g., "rsvp|yes|uuid", "rsvp|no|uuid", "rsvp|maybe|uuid")
                if len(parts) == 3 and parts[0] == "rsvp":
                    status = parts[1]  # "yes", "no", "maybe"
                    reg_id_from_btn = parts[2]
                    
                    if status not in ["yes", "no", "maybe"]:
                        logger.error(f"[RSVP-BUTTON] Invalid status: {status}")
                        return JsonResponse({"ok": True}, status=200)
                    
                    logger.warning(f"[RSVP-BUTTON] status={status!r} reg={reg.id}")
                    
                    # Call existing RSVP webhook to trigger WebSocket broadcasts
                    import requests
                    import os
                    from django.utils import timezone
                    
                    try:
                        # Call the RSVP webhook
                        webhook_url = request.build_absolute_uri("/api/webhooks/whatsapp-rsvp/")
                        response = requests.post(
                            webhook_url,
                            json={
                                "rsvp_status": status,
                                "event_registration_id": str(reg.id),
                                "responded_on": timezone.now().isoformat()
                            },
                            headers={"X-Webhook-Token": os.getenv("DJANGO_RSVP_SECRET", "")},
                            timeout=5
                        )
                        
                        if response.status_code == 200:
                            logger.warning(f"[RSVP-BUTTON] Successfully updated RSVP to {status} for {reg.id}")
                        else:
                            logger.error(f"[RSVP-BUTTON] Webhook returned {response.status_code}")
                    except Exception as exc:
                        logger.exception(f"[RSVP-BUTTON] Failed to call webhook: {exc}")
                    
                    # Send appropriate response based on status
                    if status == "yes":
                        # Ask for guest count
                        try:
                            send_freeform_text(
                                reg.guest.phone,
                                "Great! How many people will be attending (including you)? 👥\n\n"
                                "Please reply with a number (e.g., 2, 3, 4)"
                            )
                            # Set flag to expect guest count
                            sess = reg.travel_capture
                            sess.state = sess.state or {}
                            sess.state["awaiting_guest_count"] = True
                            sess.save(update_fields=["state"])
                        except Exception as exc:
                            logger.exception(f"[RSVP-BUTTON] Failed to send guest count prompt: {exc}")
                    
                    elif status == "no":
                        # Send decline confirmation
                        try:
                            send_freeform_text(
                                reg.guest.phone,
                                "Thank you for letting us know.\n\n"
                                "Your RSVP has been updated to: Not Attending ❌\n\n"
                                "We hope to see you at future events!"
                            )
                        except Exception as exc:
                            logger.exception(f"[RSVP-BUTTON] Failed to send decline confirmation: {exc}")
                    
                    elif status == "maybe":
                        # Send maybe confirmation
                        try:
                            send_freeform_text(
                                reg.guest.phone,
                                "No problem! Your RSVP has been updated to: Maybe 🤔\n\n"
                                "Please let us know when you decide!"
                            )
                        except Exception as exc:
                            logger.exception(f"[RSVP-BUTTON] Failed to send maybe confirmation: {exc}")
                    
                    return JsonResponse({"ok": True}, status=200)
                
                # Handle travel capture buttons (e.g., "tc|step|value")
                elif len(parts) == 3 and parts[0] == "tc":
                    step, value = parts[1], parts[2]
            except Exception:
                logger.error(f"[BUTTON-ERR] Malformed button_id: {btn_id}")

        if step and value:
            try:
                logger.warning(
                    f"[WEBHOOK-BUTTON] step={step!r} value={value!r} reg={reg.id}"
                )
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
# import logging

# logger = logging.getLogger("whatsapp")

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
#         logger.warning(f"[WEBHOOK] INcCOMING WA PAYLOAD: {body}")
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
#         logger.warning(f"[WAKE] Registration={reg.id} WAKE triggered")
#         resume_or_start(reg)
#         return JsonResponse({"ok": True}, status=200)

#     # --- kind: text (free-text reply for non-choice steps)
#     # if kind == "text":
#     #     text = (body.get("text") or "").strip()
#     #     if not text:
#     #         return JsonResponse({"ok": True}, status=200)

#     #     reply_text, done, is_button_step = handle_inbound_answer(reg, text)

#     #     if is_button_step:
#     #         # next question is a button step → orchestrator must send it
#     #         send_next_prompt(reg)
#     #     else:
#     #         # plain prompt → text only
#     #         if reply_text:
#     #             send_freeform_text(reg.guest.phone, reply_text)

#     #     return JsonResponse({"ok": True}, status=200)
#     # --- kind: text (free-text reply for non-choice steps)
#     if kind == "text":
#         text = (body.get("text") or "").strip()
#         if not text:
#             return JsonResponse({"ok": True}, status=200)

#         # handle_inbound_answer returns (reply_text, done_flag)
#         reply_text, done = handle_inbound_answer(reg, text)

#         if reply_text:
#             # Always send the next question as plain text here.
#             # Choice steps are handled via buttons when we call send_next_prompt()
#             # from resume/start or button flows.
#             send_freeform_text(reg.guest.phone, reply_text)

#         return JsonResponse({"ok": True}, status=200)
