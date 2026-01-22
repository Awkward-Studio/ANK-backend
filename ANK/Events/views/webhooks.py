import json
import logging
import os
import uuid
from datetime import datetime, timedelta
from datetime import timezone as tz

from django.http import HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.utils import timezone as dj_tz  # ← use alias; never shadow inside functions
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from Events.models.event_registration_model import EventRegistration
from Events.models.wa_send_map import WaSendMap
from Events.models.whatsapp_message_log import WhatsAppMessageLog
from Events.serializers.whatsapp_message_log_serializer import (
    WhatsAppMessageLogSerializer,
)
from rest_framework.pagination import PageNumberPagination
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny

log = logging.getLogger(__name__)


def _get_header_token(request) -> str:
    return (
        request.headers.get("X-Webhook-Token")
        or request.META.get("HTTP_X_WEBHOOK_TOKEN")
        or ""
    )


def _get_secret() -> str:
    return os.getenv("DJANGO_RSVP_SECRET", "")


def _norm_digits(s: str) -> str:
    # Keep digits only; store last 10–15 for resilience.
    d = "".join(ch for ch in (s or "") if ch.isdigit())
    return d[-15:]


def _ensure_aware(dt: datetime) -> datetime:
    """Make datetime timezone-aware in UTC if naive."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=tz.utc)
    return dt


@csrf_exempt
@require_http_methods(["POST"])
def track_send(request):
    hdr = (_get_header_token(request) or "").strip()
    log.warning(f"[SECRET] {hdr}")
    secret = _get_secret().strip()
    if not secret or hdr != secret:
        return HttpResponseForbidden("invalid token")

    try:
        body = json.loads(request.body.decode("utf-8"))
    except Exception:
        return HttpResponseBadRequest("invalid json")

    wa_id = _norm_digits(body.get("wa_id", ""))
    event_id = body.get("event_id")
    reg_id = body.get("event_registration_id") or ""
    template_wamid = body.get("template_wamid") or None
    flow_type = (body.get("flow_type") or "").strip() or None
    message_type = body.get("message_type") or flow_type or "rsvp"
    body_text = body.get("body") or body.get("message") or body.get("text")
    media_url = body.get("media_url")
    media_type_arg = body.get("media_type") # specific media type (image, video)
    media_id = body.get("media_id")
    sender_phone_number_id = body.get("sender_phone_number_id") # Multi-number support
    campaign_id = body.get("campaign_id") # Broadcast campaign support

    log.info(
        "track_send body=%s wa_id=%s event_id=%s reg_id=%s flow_type=%s campaign_id=%s",
        body,
        wa_id,
        event_id,
        reg_id,
        flow_type,
        campaign_id,
    )

    if not wa_id:
        return HttpResponseBadRequest("missing wa_id")

    # Check if this is a standalone message (no event/registration context)
    # This supports bulk-send and other template messages sent outside event flows
    direction = body.get("direction") or "outbound"
    is_standalone = not event_id and not reg_id

    if is_standalone:
        # For standalone messages, we create a log entry.
        # - OUTBOUND: Requires template_wamid to create WaSendMap and break stickiness
        # - INBOUND: No template_wamid needed, just log the message

        is_inbound = direction == "inbound"

        if not is_inbound and not template_wamid:
            # Outbound standalone messages require template_wamid
            return HttpResponseBadRequest(
                "missing template_wamid for outbound standalone message"
            )

        try:
            template_name = body.get("template_name")
            guest_name = body.get("guest_name")

            # For inbound messages, generate a unique wamid if not provided
            effective_wamid = template_wamid
            if is_inbound and not effective_wamid:
                effective_wamid = f"inbound-{wa_id}-{dj_tz.now().timestamp()}"

            # Try to find guest name from previous logs if not provided
            if not guest_name and is_inbound:
                previous_log = (
                    WhatsAppMessageLog.objects.filter(
                        recipient_id__endswith=wa_id[-10:], guest_name__isnull=False
                    )
                    .exclude(guest_name="")
                    .order_by("-sent_at")
                    .first()
                )
                if previous_log:
                    guest_name = previous_log.guest_name

            # 1. Create Message Log
            log_status = "received" if is_inbound else "sent"
            WhatsAppMessageLog.objects.update_or_create(
                wamid=effective_wamid,
                defaults={
                    "recipient_id": wa_id,
                    "status": log_status,
                    "sent_at": dj_tz.now(),
                    "event_registration_id": None,
                    "event_id": None,
                    "template_name": template_name,
                    "flow_type": flow_type or "standalone",
                    "message_type": message_type or ("text" if is_inbound else "template"),
                    "direction": direction,
                    "guest_id": None,
                    "guest_name": guest_name,
                    "body": body_text,
                    "media_url": media_url,
                    "media_type": media_type_arg,
                    "media_id": media_id,
                    "sender_phone_number_id": sender_phone_number_id,
                    "campaign_id": campaign_id,
                },
            )
            log.info(
                f"[TRACK-SEND][STANDALONE] Created message log for wamid={effective_wamid[:30]}... direction={direction}"
            )

            # 2. Create WaSendMap (Standalone Context) - Only for OUTBOUND
            # For inbound, we don't need to break stickiness
            if not is_inbound and template_wamid:
                defaults = {
                    "wa_id": wa_id,
                    "event": None,
                    "event_registration": None,
                    "expires_at": dj_tz.now() + timedelta(days=4),
                    "flow_type": flow_type or "standalone",
                    "sender_phone_number_id": sender_phone_number_id,
                }
                obj, _ = WaSendMap.objects.update_or_create(
                    template_wamid=template_wamid, defaults=defaults
                )
                log.info(f"[TRACK-SEND][STANDALONE] Created WaSendMap for {wa_id}")

        except Exception as log_err:
            log.warning(
                f"[TRACK-SEND][STANDALONE] Failed to create log/map: {log_err}"
            )
            return JsonResponse({"ok": False, "error": str(log_err)}, status=500)

        return JsonResponse({"ok": True, "standalone": True, "wamid": effective_wamid})

    # Regular flow - requires event_id for event-based messages
    if not event_id:
        return HttpResponseBadRequest("missing event_id")

    # Try resolve registration
    er = None
    if reg_id:
        try:
            er = EventRegistration.objects.select_related("event").get(pk=reg_id)
        except EventRegistration.DoesNotExist:
            return HttpResponseBadRequest("registration not found")

    if not er:
        er = (
            EventRegistration.objects.filter(event_id=event_id)
            .order_by("-created_at")
            .first()
        )
        if not er:
            return HttpResponseBadRequest("could not resolve registration")

    # Upsert map
    try:
        defaults = {
            "wa_id": wa_id,
            "event": er.event,
            "event_registration": er,
            "expires_at": dj_tz.now() + timedelta(days=4),
            "flow_type": flow_type,
            "sender_phone_number_id": sender_phone_number_id,
        }
        if template_wamid:
            obj, _ = WaSendMap.objects.update_or_create(
                template_wamid=template_wamid, defaults=defaults
            )
        else:
            if not flow_type:
                # If flow_type is missing for a generic message, log an error or default
                # to creating a new, non-reusable map to avoid conflicts.
                log.warning(
                    f"track_send: Missing flow_type for generic map for reg={er.id}. Creating new map."
                )
                obj = WaSendMap.objects.create(**defaults)
            else:
                # This uses the new unique constraint:
                # (wa_id, sender_phone_number_id, event_registration, flow_type, template_wamid=NULL)
                obj, _ = WaSendMap.objects.update_or_create(
                    wa_id=wa_id,
                    sender_phone_number_id=sender_phone_number_id,
                    event_registration=er,
                    flow_type=flow_type,
                    template_wamid__isnull=True,
                    defaults=defaults,
                )
    except Exception as e:
        log.exception("track_send failed")
        return HttpResponseBadRequest(f"track_send error: {e}")

    # Update EventRegistration status to "pending" if not yet responded
    try:
        if er.rsvp_status == "pending":
            # Only update initiated_on if not already set
            if not er.initiated_on:
                er.initiated_on = dj_tz.now()
                er.save(update_fields=["initiated_on"])
                log.info(
                    f"Updated registration {er.id}: set initiated_on for event {er.event_id}"
                )
    except Exception as update_err:
        # Log error but don't fail the request
        log.error(
            f"Failed to update RSVP status for registration {er.id}: {update_err}"
        )

    # Create WhatsAppMessageLog entry for delivery tracking
    if template_wamid:
        try:
            template_name = body.get("template_name")
            guest_id = body.get("guest_id")
            guest_name = body.get("guest_name")
            message_type = body.get("message_type") or flow_type or "rsvp"

            WhatsAppMessageLog.objects.update_or_create(
                wamid=template_wamid,
                defaults={
                    "recipient_id": wa_id,
                    "status": "sent",
                    "sent_at": dj_tz.now(),
                    "event_registration_id": str(er.id),
                    "event_id": str(event_id),
                    "template_name": template_name,
                    "flow_type": flow_type,
                    "message_type": message_type,
                    "direction": direction,
                    "guest_id": str(guest_id) if guest_id else None,
                    "guest_name": guest_name,
                    "body": body_text,
                    "media_url": media_url,
                    "media_type": media_type_arg,
                    "media_id": media_id,
                    "campaign_id": campaign_id,
                },
            )
            log.info(
                f"[TRACK-SEND] Created message log for wamid={template_wamid[:30]}..."
            )
        except Exception as log_err:
            # Non-fatal - don't fail the request if logging fails
            log.warning(f"[TRACK-SEND] Failed to create message log: {log_err}")

    # [NEW] Opt-In Request Logic
    if message_type == "utility":
        try:
            if not er.whatsapp_opt_in_token:
                er.whatsapp_opt_in_token = str(uuid.uuid4())
            
            # Update status
            er.whatsapp_opt_in_status = 'sent'
            er.whatsapp_opt_in_sent_at = dj_tz.now()
            er.save(update_fields=['whatsapp_opt_in_token', 'whatsapp_opt_in_status', 'whatsapp_opt_in_sent_at'])
            
            # Construct URL
            domain = os.getenv("FRONTEND_URL", "https://ank-events.com")
            # Frontend URL that will consume the token
            opt_in_link = f"{domain}/opt-in?token={er.whatsapp_opt_in_token}"
            
            # Send Template
            from MessageTemplates.services.whatsapp import send_template
            
            send_template(
                to_wa_id=wa_id,
                template_name="event_opt_in_request",
                components=[
                    {
                        "type": "body",
                        "parameters": [
                            {"type": "text", "text": opt_in_link}
                        ]
                    }
                ]
            )
            log.info(f"[OPT-IN] Sent request to {wa_id} for reg {er.id}")
            
        except Exception as e:
            log.exception(f"[OPT-IN] Failed to process utility message: {e}")
            # We don't return error to avoid breaking the caller if logging succeeded above

    return JsonResponse({"ok": True, "map_id": str(obj.id)})



#


@csrf_exempt
@require_http_methods(["POST"])
def whatsapp_rsvp(request):
    """
    Accepts either exact registration or resolves by mapping:
    Body (exact):
      { rsvp_status: "yes|no|maybe", event_registration_id, responded_on? }
    Body (template-only resolve):
      { rsvp_status: "yes|no|maybe", wa_id, template_wamid?, event_id?, responded_on? }
    """
    hdr = (_get_header_token(request) or "").strip()
    secret = _get_secret().strip()
    if not secret or hdr != secret:
        return HttpResponseForbidden("invalid token")

    # Parse body
    try:
        body = json.loads(request.body.decode("utf-8"))
        # [DEBUG] Log exact keys to diagnose "Yes" text vs "rsvp_status" payload
        log.warning(
            f"[RSVP-DEBUG] Incoming keys: {list(body.keys())} | "
            f"rsvp_status={body.get('rsvp_status')} | "
            f"body={body.get('body')} | "
            f"reg_id={body.get('event_registration_id')}"
        )
    except Exception:
        return HttpResponseBadRequest("invalid json")

    # Get the incoming status/body and media
    raw_status = (body.get("rsvp_status") or body.get("body") or "").strip()
    media_id = body.get("media_id")
    media_type = body.get("media_type")
    
    # [FIX] Check for Travel Capture (tc|) buttons that might be sent here
    # This happens when a user clicks "Add Travel Details" on the RSVP confirmation message
    button_id = body.get("button_id") or ""
    effective_payload = button_id if button_id.startswith("tc|") else (raw_status if raw_status.startswith("tc|") else "")

    if effective_payload:
        from MessageTemplates.services.travel_info_capture import apply_button_choice
        
        parts = effective_payload.split("|", 2)
        if len(parts) >= 2:
            step = parts[1]
            value = parts[2] if len(parts) > 2 else ""
            
            # We need the registration to apply the choice
            er_target = None
            req_reg_id = body.get("event_registration_id")
            
            if req_reg_id:
                try:
                    er_target = EventRegistration.objects.get(pk=req_reg_id)
                except EventRegistration.DoesNotExist:
                    pass
            
            if not er_target:
                 # Try resolve by wa_id if reg_id missing in payload
                 w_id = _norm_digits(body.get("wa_id", ""))
                 if w_id:
                     er_target = EventRegistration.objects.filter(guest__phone__endswith=w_id).order_by("-created_at").first()

            if er_target:
                log.info(f"[RSVP-WEBHOOK] Delegating button {effective_payload} to Travel Capture for reg {er_target.id}")
                try:
                    apply_button_choice(er_target, step, value)
                    return JsonResponse({"ok": True, "delegated": True})
                except Exception as e:
                    log.exception(f"[RSVP-WEBHOOK] Travel delegation failed: {e}")
                    # Fall through to standard logging? Or return error?
                    pass


    
    # [CONTEXT-AWARE LOGIC]
    # We always need the latest conversation state (WaSendMap) to determine implicit context.
    latest_map = None
    wa_id = _norm_digits(body.get("wa_id", ""))
    # ✅ FIX: Support both field names (frontend sends "sender_phone_number_id")
    to_phone_number_id = body.get("sender_phone_number_id") or body.get("to_phone_number_id")
    if wa_id:
        latest_map_qs = WaSendMap.objects.filter(
            wa_id=wa_id,
            expires_at__gt=dj_tz.now()
        )
        if to_phone_number_id:
            latest_map_qs = latest_map_qs.filter(sender_phone_number_id=to_phone_number_id)
        latest_map = latest_map_qs.order_by("-created_at").values("flow_type", "event_registration", "created_at").first()
    
    current_flow = latest_map.get("flow_type") if latest_map else None

    # [DEBUG LOGGING]
    log.warning(f"[RSVP-CONTEXT] wa_id={wa_id} | latest_map_id={latest_map} | current_flow={current_flow}")

    # [FIX] CHECK FOR EXPLICIT SOURCE (Trust Levels)
    # 1. Internal API Call (from buttons code) -> TRUSTED
    is_internal_button = body.get("source") == "internal_button"
    # 2. Direct Button Payload -> TRUSTED
    has_button_id = bool(body.get("button_id"))
    # 3. Explicit 'rsvp_status' (could be text forwarder) -> CHECK CONTEXT
    explicit_rsvp_status = body.get("rsvp_status")

    if is_internal_button or has_button_id:
         # ALWAYS TRUST explicit button actions/internal calls regardless of flow state.
         is_explicit_action = True
    else:
         is_explicit_action = False

    log.warning(f"[RSVP-CHECK] is_internal={is_internal_button} | has_btn={has_button_id} | explicit_status={explicit_rsvp_status} | is_explicit={is_explicit_action}")

    # Determine is_rsvp
    # If Explicit Action -> True (if status present)
    # If Text -> True ONLY IF current_flow is 'rsvp'.
    
    # ✅ Normalize to title case
    status_map = {
        "yes": "Yes",
        "no": "No",
        "maybe": "Maybe",
        "pending": "Pending",
        "not_sent": "Not_Sent",
    }

    normalized_status = status_map.get(raw_status.lower())

    if explicit_rsvp_status and normalized_status:
        if is_explicit_action:
             is_rsvp = True
             log.info("[RSVP-DECISION] ALLOWED (Explicit Source)")
        else:
             # Text / Implicit
             if current_flow == "rsvp":
                  is_rsvp = True
                  log.info(f"[RSVP-DECISION] ALLOWED (Context: rsvp) | text='{raw_status}'")
             else:
                  is_rsvp = False
                  log.warning(f"[RSVP-DECISION] BLOCKED (Context Mismatch) | text='{raw_status}' | current_flow='{current_flow}'")
    else:
        is_rsvp = False

    log.info(f"[RSVP-FINAL] is_rsvp={is_rsvp}")


    responded_on = None
    if body.get("responded_on"):
        parsed = parse_datetime(body["responded_on"])
        responded_on = _ensure_aware(parsed) if parsed else datetime.now(tz=tz.utc)
    else:
        responded_on = datetime.now(tz=tz.utc)

    # Resolve registration
    er = None
    reg_id = body.get("event_registration_id")
    if reg_id:
        try:
            er = EventRegistration.objects.get(pk=reg_id)
        except EventRegistration.DoesNotExist:
            return HttpResponseBadRequest("registration not found")
    else:
        # Fallback resolution if reg_id missing (e.g. text message)
        # Use latest_map if available (Stickiness)
        if latest_map and latest_map.get("event_registration"):
             try:
                 er = EventRegistration.objects.get(pk=latest_map["event_registration"])
             except EventRegistration.DoesNotExist:
                 pass
        
        # ... standard resolution callbacks ...
        if not er and wa_id:
             # Try template_wamid / event_id / or just recent
             pass # (We rely on logic below or existing generic resolution if we want to keep it)
        
        # [Simplify: If we have latest_map, we trust it for context resolution]
        if not er:
            # Re-run strict search if latest_map failed or wasn't used
             wa_digits = _norm_digits(body.get("wa_id", ""))
             if to_phone_number_id:
                 # ... (existing logic) ...
                 pass
             
             # (Keeping existing fallback blocks intact below for safety, 
             #  but usually latest_map logic above solves it for active sessions)
             pass


    if not er:
        # Standard resolution block (kept from original code to ensure safely finding context)
        wa_id = _norm_digits(body.get("wa_id", ""))

        base_qs = WaSendMap.objects.filter(wa_id=wa_id, expires_at__gt=dj_tz.now())
        if to_phone_number_id:
            base_qs = base_qs.filter(sender_phone_number_id=to_phone_number_id)

        if body.get("template_wamid"):
            rid = base_qs.filter(template_wamid=body.get("template_wamid")).values_list("event_registration", flat=True).first()
            if rid: er = EventRegistration.objects.get(pk=rid)

        if not er and body.get("event_id"):
            rid = base_qs.filter(event_id=body.get("event_id")).values_list("event_registration", flat=True).first()
            if rid: er = EventRegistration.objects.get(pk=rid)

        if not er:
            # Final fallback: Just latest
            rid = base_qs.order_by("-created_at").values_list("event_registration", flat=True).first()
            if rid: er = EventRegistration.objects.get(pk=rid)


    # [Universal Command Handling]
    # Intercept "menu", "hi", "help", etc. to show options regardless of flow state.
    universal_commands = {"menu", "options", "help", "hi", "hello", "start", "restart", "test"}
    stop_commands = {"stop", "unsubscribe"}
    
    normalized_cmd = raw_status.lower().strip()
    is_menu_command = normalized_cmd in universal_commands
    is_stop_command = normalized_cmd in stop_commands

    if is_stop_command:
         # Handle Opt-Out
         if er:
             er.whatsapp_opt_in_status = 'opt_out'
             er.save(update_fields=['whatsapp_opt_in_status'])
             
             from MessageTemplates.services.whatsapp import send_freeform_text
             try:
                 # Multi-number support: Use default number for system messages
                 msg_id, sender_id = send_freeform_text(wa_id, "You have been unsubscribed from updates for this event.", phone_number_id=None)
                 log.info(f"[OPT-OUT] Sent unsubscribe confirmation to {wa_id} from {sender_id}")
             except Exception:
                 pass
             
             log.info(f"[OPT-OUT] Unsubscribed {wa_id} (reg {er.id})")
             return JsonResponse({"ok": True, "status": "opt_out"})
         else:
             # TODO: Global unsubscribe if no ER found?
             # For now, just log it.
             log.info(f"[OPT-OUT] Received STOP from {wa_id} but no active registration context found.")

    if is_menu_command and not er:
        # Try global lookup by phone if context is missing
        if wa_id:
            wa_digits = _norm_digits(wa_id)
            # Find latest future event or recent past
            er = EventRegistration.objects.filter(
                guest__phone__endswith=wa_digits
            ).order_by("-event__start_date", "-created_at").first()
            if er:
                log.info(f"[MENU-LOOKUP] Found reg {er.id} for {wa_id}")

    if is_menu_command and er:
        from Events.services.message_logger import MessageLogger
        
        # Log the inbound command
        MessageLogger.log_inbound(
            event_registration=er,
            content=raw_status,
            message_type="custom",
            wa_message_id=body.get("wa_id", ""),
            metadata=body,
            sender_phone_number_id=to_phone_number_id
        )
        
        # Send Menu Buttons
        event_name = er.event.name if er.event else "the event"
        msg = f"👋 Hello! Here are your options for {event_name}:"
        buttons = [
            {"id": f"tc|start_travel|{er.id}", "title": "✈️ Add Travel Info"},
            {"id": f"tc|update_rsvp_menu|{er.id}", "title": "📝 Update RSVP"},
            {"id": f"tc|remind_later|{er.id}", "title": "⏰ Remind Later"},
        ]
        MessageLogger.send_buttons(er, msg, buttons, "system")
        
        return JsonResponse({"ok": True, "menu_sent": True})
    
    elif is_menu_command and not er:
        # Command sent but user unknown -> Send helpful text + fall through to logging
        if wa_id:
            from MessageTemplates.services.whatsapp import send_freeform_text
            try:
                # Multi-number support: Use default number for unknown user messages
                msg_id, sender_id = send_freeform_text(wa_id, "👋 We couldn't find any active events linked to this number. Please contact the admin.", phone_number_id=None)
                log.info(f"[UNKNOWN-USER] Sent help message to {wa_id} from {sender_id}")
            except Exception:
                pass
        # Fall through to 'if not er' block below for standard standalone logging

    if not er:
        # STANDALONE / UNREGISTERED MESSAGE HANDLING
        # If we cannot resolve a registration, we still want to log this message
        # so it appears in the Bulk Chat History (standalone view).
        
        # Create a log entry for this unknown inbound message
        from Events.models.whatsapp_message_log import WhatsAppMessageLog

        # [NEW] Try to find a name from previous logs for this number
        previous_log_with_name = (
            WhatsAppMessageLog.objects.filter(
                recipient_id=_norm_digits(wa_id)[-15:], guest_name__isnull=False
            )
            .exclude(guest_name="")
            .order_by("-sent_at")
            .first()
        )
        found_name = previous_log_with_name.guest_name if previous_log_with_name else None

        WhatsAppMessageLog.objects.create(
            wamid=body.get("wa_id", "") or f"unknown-{dj_tz.now().timestamp()}",
            recipient_id=_norm_digits(wa_id)[
                -15:
            ],  # [FIX] Normalize to digits only for consistency
            status="received",
            sent_at=responded_on,
            direction="inbound",
            body=raw_status,
            message_type="custom",
            flow_type="standalone",
            guest_name=found_name,
            media_id=media_id,
            media_type=media_type,
        )
        
        log.info(f"[WEBHOOK] Logged standalone inbound message from {wa_id} (media={bool(media_id)})")
        return JsonResponse({"ok": True, "standalone": True})
        
        # Old behavior: return HttpResponseBadRequest("no mapping found for wa_id")

        return JsonResponse({"ok": True, "standalone": True})
        
        # Old behavior: return HttpResponseBadRequest("no mapping found for wa_id")

    
    # [FIX] DELEGATE TO TRAVEL CAPTURE IF ACTIVE FLOW IS TRAVEL
    # Use the `current_flow` we fetched at the top
    if current_flow == "travel":
        # We are in Travel Flow -> All text input should go to the travel orchestrator
        # unless it's a specialized command like "menu" (handled above)
        
        # Ensure we have the registration (er is resolved)
        if er and not is_menu_command:
            try:
                from MessageTemplates.services.travel_info_capture import handle_inbound_answer
                log.info(f"[WEBHOOK] Delegating text '{raw_status}' to Travel Flow for reg {er.id}")
                
                reply_text, flow_done = handle_inbound_answer(er, raw_status)
                
                if reply_text:
                    from Events.services.message_logger import MessageLogger
                    MessageLogger.send_text(er, reply_text, "travel")
                
                return JsonResponse({"ok": True, "delegated_travel": True})
            except Exception as e:
                log.exception(f"[WEBHOOK] Failed to delegate to travel flow: {e}")


    # [REMOVED OLD STRICT FLOW CHECK - We integrated it into is_rsvp determination above]


    # Update RSVP only if it's a valid RSVP command
    if is_rsvp:
        er.rsvp_status = normalized_status
        er.save(update_fields=["rsvp_status"])
        log.info(f"Updated RSVP status to '{normalized_status}' for registration {er.id}")

    # Log inbound message
    from Events.services.message_logger import MessageLogger

    # Determine display content
    if is_rsvp:
        display_content = f"RSVP: {normalized_status}"
        msg_type = "rsvp"
    else:
        display_content = raw_status # Generic text
        msg_type = "custom"

    MessageLogger.log_inbound(
        event_registration=er,
        content=display_content,
        message_type=msg_type,
        wa_message_id=body.get("wa_id", ""),
        media_id=media_id,
        media_type=media_type,
        metadata=body,
        sender_phone_number_id=body.get("to_phone_number_id"),
    )

    # Send immediate WhatsApp confirmation with next steps
    if is_rsvp:
        try:
            from Events.services.message_logger import MessageLogger as MsgLogger

            event_name = er.event.name if er.event else "the event"

            if normalized_status == "Yes":
                # Check if user has extra pax to confirm
                estimated = er.estimated_pax or 1
                has_extras = er.extra_attendees.exists()
                
                if estimated > 1 or has_extras:
                    # Ask for pax confirmation before final RSVP confirmation
                    extra_count = estimated - 1 if estimated > 1 else er.extra_attendees.count()
                    total_pax = estimated if estimated > 1 else (1 + er.extra_attendees.count())
                    
                    # Build guest list if ExtraAttendee records exist
                    guest_list = ""
                    extras = list(er.extra_attendees.all()[:5])  # Limit to 5 for message length
                    if extras:
                        guest_list = "\n\nRegistered guests:\n"
                        for i, ex in enumerate(extras, 1):
                            guest_list += f"  {i}. {ex.name}\n"
                        if er.extra_attendees.count() > 5:
                            guest_list += f"  ... and {er.extra_attendees.count() - 5} more\n"
                    
                    message = (
                        f"✅ Great! We have recorded *{total_pax}* guests for your party.{guest_list}\n\n"
                        f"How many of you are attending {event_name}?"
                    )
                    
                    buttons = [
                        {"id": f"tc|rsvp_pax_confirm|{total_pax}", "title": f"All {total_pax} guests"},
                        {"id": f"tc|rsvp_pax_confirm|1", "title": "Just me (1)"},
                    ]
                    # Add a third option if there's room and pax > 2
                    if total_pax > 2:
                        buttons.append({"id": f"tc|rsvp_pax_custom|{er.id}", "title": "Different number"})
                    
                    MsgLogger.send_buttons(er, message, buttons, "rsvp")
                    log.info(f"[RSVP] Sent pax confirmation request to {er.guest.phone} (recorded: {total_pax})")
                else:
                    # No extra pax - send direct confirmation
                    message = (
                        f"✅ Perfect! Your RSVP has been confirmed for {event_name}.\n\n"
                        "We're looking forward to seeing you! 🎉\n\n"
                        "What would you like to do next?"
                    )
                    buttons = [
                        {"id": f"tc|start_travel|{er.id}", "title": "Add Travel Details"},
                        {"id": f"tc|update_rsvp_menu|{er.id}", "title": "Update RSVP"},
                        {"id": f"tc|remind_later|{er.id}", "title": "Remind Me Later"},
                    ]
                    MsgLogger.send_buttons(er, message, buttons, "rsvp")
                    log.info(f"[RSVP] Sent post-RSVP options to {er.guest.phone}")

            elif normalized_status == "No":
                # For "No" - simple confirmation
                message = (
                    f"Thank you for letting us know.\n\n"
                    f"Your RSVP has been updated to: Not Attending ❌\n\n"
                    "We hope to see you at future events!"
                )
                MsgLogger.send_text(er, message, "rsvp")
                log.info(f"[RSVP] Sent decline confirmation to {er.guest.phone}")

            elif normalized_status == "Maybe":
                # For "Maybe" - simple confirmation
                message = (
                    f"No problem! Your RSVP has been updated to: Maybe 🤔\n\n"
                    "Please let us know when you decide!"
                )
                MsgLogger.send_text(er, message, "rsvp")
                log.info(f"[RSVP] Sent maybe confirmation to {er.guest.phone}")

        except Exception as msg_err:
            log.exception(f"[RSVP] Failed to send confirmation message: {msg_err}")
            # Don't fail the request if message sending fails

    # Mark WaSendMap consumed (non-fatal if it fails)
    try:
        wa_id = _norm_digits(body.get("wa_id", ""))
        template_wamid = body.get("template_wamid") or None
        event_id = body.get("event_id") or None

        qs = WaSendMap.objects.filter(event_registration=er)
        if template_wamid:
            qs = qs.filter(template_wamid=template_wamid)
        elif wa_id and event_id:
            qs = qs.filter(wa_id=wa_id, event_id=event_id)
        elif wa_id:
            qs = qs.filter(wa_id=wa_id)

        qs.update(consumed_at=dj_tz.now())
    except Exception as e:
        log.warning("Failed to mark WaSendMap consumed: %s", e)

    return JsonResponse(
        {
            "ok": True,
            "id": str(er.id),
            "event": str(er.event_id),
            "guest": str(er.guest_id),  # ensure JSON-safe
            "rsvp_status": er.rsvp_status,
            "responded_on": er.responded_on.isoformat() if er.responded_on else None,
        }
    )


@csrf_exempt
@require_http_methods(["GET"])
def resolve_wa(request, wa_id):
    token = request.headers.get("X-Webhook-Token", "")
    if token != os.getenv("DJANGO_RSVP_SECRET"):
        return JsonResponse({"ok": False, "error": "forbidden"}, status=403)

    from django.utils import timezone

    from Events.models.wa_send_map import WaSendMap

    wa_digits = "".join(c for c in wa_id if c.isdigit())[-15:]

    row = (
        WaSendMap.objects.filter(wa_id=wa_digits, expires_at__gt=timezone.now())
        .order_by("-created_at")
        .values("event_id", "event_registration_id", "flow_type")
        .first()
    )

    if not row:
        return JsonResponse({"ok": False, "found": False})

    return JsonResponse(
        {
            "ok": True,
            "found": True,
            "event_id": row["event_id"],
            "registration_id": row["event_registration_id"],
            "flow_type": row.get("flow_type"),
        }
    )


@csrf_exempt
@require_http_methods(["POST"])
def message_status_webhook(request):
    """
    Receive status updates from Next.js webhook (forwarded from Meta).

    POST /api/webhooks/message-status/
    {
        "wamid": "wamid.xxx...",
        "recipient_id": "919876543210",
        "status": "delivered" | "read" | "failed",
        "timestamp": "2024-01-15T10:30:00Z",
        "errors": [{"code": 131026, "title": "..."}]  // if failed
    }
    """
    # Verify webhook token
    token = _get_header_token(request)
    secret = _get_secret()
    if not secret or token != secret:
        return HttpResponseForbidden("invalid token")

    try:
        body = json.loads(request.body.decode("utf-8"))
    except Exception:
        return HttpResponseBadRequest("invalid json")

    wamid = body.get("wamid")
    status = body.get("status")
    timestamp_str = body.get("timestamp")
    errors = body.get("errors")
    recipient_id = _norm_digits(body.get("recipient_id", ""))

    if not wamid or not status:
        return HttpResponseBadRequest("missing wamid or status")

    try:
        # Parse timestamp
        ts = None
        if timestamp_str:
            parsed = parse_datetime(timestamp_str)
            ts = _ensure_aware(parsed) if parsed else dj_tz.now()
        else:
            ts = dj_tz.now()

        # Get or create the message log
        msg_log, created = WhatsAppMessageLog.objects.get_or_create(
            wamid=wamid,
            defaults={
                "recipient_id": recipient_id,
                "status": status,
                "sent_at": ts,
            },
        )

        # Update status (only upgrade, never downgrade - except for failed)
        status_order = {"sent": 1, "delivered": 2, "read": 3, "failed": 0}
        current_order = status_order.get(msg_log.status, 0)
        new_order = status_order.get(status, 0)

        if new_order > current_order or status == "failed":
            msg_log.status = status

            # Set timestamp based on status
            if status == "delivered":
                msg_log.delivered_at = ts
            elif status == "read":
                msg_log.read_at = ts
            elif status == "failed":
                msg_log.failed_at = ts
                if errors and len(errors) > 0:
                    msg_log.error_code = str(errors[0].get("code", ""))
                    msg_log.error_message = errors[0].get("title", "") or errors[0].get(
                        "message", ""
                    )
                log.warning(
                    f"[MESSAGE-STATUS] FAILED wamid={wamid[:50]}... "
                    f"recipient={recipient_id} error_code={msg_log.error_code} "
                    f"error_message={msg_log.error_message} raw_errors={errors}"
                )

            msg_log.save()
            log.info(f"[MESSAGE-STATUS] Updated {wamid[:30]}... to {status}")

        return JsonResponse({"ok": True, "status": msg_log.status})

    except Exception as e:
        log.exception(f"[MESSAGE-STATUS] Error processing status update: {e}")
        return JsonResponse({"ok": False, "error": str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def message_status_lookup(request):
    """
    Look up current status of messages by wamid.

    POST /api/webhooks/message-status-lookup/
    {
        "wamids": ["wamid1", "wamid2", ...]
    }

    Returns:
    {
        "statuses": {
            "wamid1": {"status": "delivered", "delivered_at": "..."},
            "wamid2": {"status": "read", "read_at": "..."},
            ...
        }
    }
    """
    # Verify webhook token
    token = _get_header_token(request)
    secret = _get_secret()
    if not secret or token != secret:
        return HttpResponseForbidden("invalid token")

    try:
        body = json.loads(request.body.decode("utf-8"))
    except Exception:
        return HttpResponseBadRequest("invalid json")

    wamids = body.get("wamids", [])

    if not wamids:
        return JsonResponse({"statuses": {}})

    try:
        logs = WhatsAppMessageLog.objects.filter(wamid__in=wamids)

        statuses = {}
        for msg_log in logs:
            statuses[msg_log.wamid] = {
                "status": msg_log.status,
                "error": msg_log.error_message if msg_log.status == "failed" else None,
                "error_code": msg_log.error_code
                if msg_log.status == "failed"
                else None,
                "sent_at": msg_log.sent_at.isoformat() if msg_log.sent_at else None,
                "delivered_at": msg_log.delivered_at.isoformat()
                if msg_log.delivered_at
                else None,
                "read_at": msg_log.read_at.isoformat() if msg_log.read_at else None,
            }

        return JsonResponse({"statuses": statuses})

    except Exception as e:
        log.exception(f"[MESSAGE-STATUS-LOOKUP] Error: {e}")
        return JsonResponse({"ok": False, "error": str(e)}, status=500)


@api_view(["GET"])
@permission_classes([AllowAny])
def message_logs(request):
    """
    Get message logs filtered by registration, event, guest, or recipient phone.

    GET /api/webhooks/message-logs/
    Query params:
        - registration_id: Filter by registration
        - event_id: Filter by event
        - guest_id: Filter by guest
        - recipient_id: Filter by recipient phone number (for standalone messages)
        - sender_phone_number_id: Filter by sender phone number (multi-number support)
        - template_name: Filter by template name
        - standalone: If "true", only return messages without event/registration context

    Returns:
    {
        "logs": [
            {
                "id": "uuid",
                "wamid": "wamid.xxx...",
                "recipient_id": "919876543210",
                "status": "delivered",
                "message_type": "rsvp",
                "template_name": null,
                "event_id": "uuid",
                "registration_id": "uuid",
                "guest_id": "uuid",
                "guest_name": "John Doe",
                "sent_at": "2024-01-15T10:30:00Z",
                "delivered_at": "2024-01-15T10:30:05Z",
                "read_at": null,
                "error_code": null,
                "error_message": null
            }
        ]
    }
    """
    # Verify webhook token
    token = _get_header_token(request)
    secret = _get_secret()
    if not secret or token != secret:
        return JsonResponse({"detail": "Invalid token"}, status=403)

    registration_id = request.GET.get("registration_id")
    event_id = request.GET.get("event_id")
    guest_id = request.GET.get("guest_id")
    recipient_id = request.GET.get("recipient_id")
    sender_phone_number_id = request.GET.get("sender_phone_number_id")  # Multi-number support
    template_name = request.GET.get("template_name")
    standalone_only = request.GET.get("standalone", "").lower() == "true"

    queryset = WhatsAppMessageLog.objects.all().order_by("-sent_at")

    if registration_id:
        queryset = queryset.filter(event_registration_id=registration_id)
    if event_id:
        queryset = queryset.filter(event_id=event_id)
    if guest_id:
        queryset = queryset.filter(guest_id=guest_id)
    if recipient_id:
        # Normalize phone number (keep last 10-15 digits)
        normalized = _norm_digits(recipient_id)
        if normalized:
             queryset = queryset.filter(recipient_id__endswith=normalized[-10:])
    if sender_phone_number_id:
        # Filter by which of OUR numbers sent/received the message (inbox segregation)
        queryset = queryset.filter(sender_phone_number_id=sender_phone_number_id)
    if template_name:
        queryset = queryset.filter(template_name=template_name)
    if standalone_only:
        queryset = queryset.filter(
            event_id__isnull=True, event_registration_id__isnull=True
        )

    # Pagination
    paginator = PageNumberPagination()
    # Default 20, max 100
    paginator.page_size = int(request.GET.get("limit", 20)) 
    paginator.max_page_size = 100
    
    result_page = paginator.paginate_queryset(queryset, request)
    serializer = WhatsAppMessageLogSerializer(result_page, many=True)
    
    return paginator.get_paginated_response(serializer.data)


@csrf_exempt
@require_http_methods(["GET"])
def message_logs_latest(request):
    """
    Get the latest message log for a registration.

    GET /api/webhooks/message-logs/latest/
    Query params:
        - registration_id: Required

    Returns:
    {
        "log": { ... } or null
    }
    """
    # Verify webhook token
    token = _get_header_token(request)
    secret = _get_secret()
    if not secret or token != secret:
        return HttpResponseForbidden("invalid token")

    registration_id = request.GET.get("registration_id")
    if not registration_id:
        return HttpResponseBadRequest("Missing registration_id")

    msg_log = (
        WhatsAppMessageLog.objects.filter(event_registration_id=registration_id)
        .order_by("-sent_at")
        .first()
    )

    if not msg_log:
        return JsonResponse({"log": None})

    return JsonResponse(
        {
            "log": {
                "id": str(msg_log.id),
                "wamid": msg_log.wamid,
                "recipient_id": msg_log.recipient_id,
                "status": msg_log.status,
                "message_type": msg_log.message_type,
                "template_name": msg_log.template_name,
                "sent_at": msg_log.sent_at.isoformat() if msg_log.sent_at else None,
                "delivered_at": msg_log.delivered_at.isoformat()
                if msg_log.delivered_at
                else None,
                "read_at": msg_log.read_at.isoformat() if msg_log.read_at else None,
                "error_code": msg_log.error_code,
                "error_message": msg_log.error_message,
            }
        }
    )
