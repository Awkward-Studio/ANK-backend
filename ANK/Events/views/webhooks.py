import os, json, logging
from datetime import datetime, timedelta, timezone as tz

from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.dateparse import parse_datetime
from django.utils import timezone as dj_tz  # ← use alias; never shadow inside functions

from Events.models.event_registration_model import EventRegistration
from Events.models.wa_send_map import WaSendMap

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
    reg_id = body.get("event_registration_id")
    template_wamid = body.get("template_wamid") or None

    log.info(
        "track_send body=%s wa_id=%s event_id=%s reg_id=%s",
        body,
        wa_id,
        event_id,
        reg_id,
    )

    if not wa_id or not event_id:
        return HttpResponseBadRequest("missing wa_id or event_id")

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
            "expires_at": dj_tz.now() + timedelta(days=30),
        }
        if template_wamid:
            obj, _ = WaSendMap.objects.update_or_create(
                template_wamid=template_wamid, defaults=defaults
            )
        else:
            obj, _ = WaSendMap.objects.update_or_create(
                wa_id=wa_id, event=er.event, defaults=defaults
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
            
            # Optional: Send WebSocket notification for real-time updates
            try:
                from channels.layers import get_channel_layer
                from asgiref.sync import async_to_sync

                channel_layer = get_channel_layer()
                if channel_layer:
                    async_to_sync(channel_layer.group_send)(
                        f"event_{er.event_id}",
                        {
                            "type": "rsvp_update",
                            "data": {
                                "type": "rsvp_sent",
                                "action": "updated",
                                "registration": {
                                    "id": str(er.id),
                                    "event": str(er.event_id),
                                    "rsvp_status": er.rsvp_status,
                                    "initiated_on": er.initiated_on.isoformat() if er.initiated_on else None,
                                },
                            },
                        },
                    )
            except Exception as ws_err:
                log.warning(f"WebSocket notification failed: {ws_err}")
    except Exception as update_err:
        # Log error but don't fail the request
        log.error(f"Failed to update RSVP status for registration {er.id}: {update_err}")

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
    except Exception:
        return HttpResponseBadRequest("invalid json")

    # Get the incoming status (lowercase from Next.js)
    raw_status = (body.get("rsvp_status") or "").strip().lower()
    
    # ✅ Normalize to title case
    status_map = {
        'yes': 'Yes',
        'no': 'No',
        'maybe': 'Maybe',
        'pending': 'Pending',
        'not_sent': 'Not_Sent'
    }
    
    normalized_status = status_map.get(raw_status)
    
    if not normalized_status or raw_status not in {"yes", "no", "maybe"}:
        log.warning(f"Unknown RSVP status received: {raw_status}")
        return HttpResponseBadRequest("invalid rsvp_status")

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
        wa_id = _norm_digits(body.get("wa_id", ""))
        template_wamid = body.get("template_wamid") or None
        event_id = body.get("event_id") or None

        if not wa_id:
            return HttpResponseBadRequest("missing wa_id")

        base_qs = WaSendMap.objects.filter(wa_id=wa_id, expires_at__gt=dj_tz.now())

        # Priority 1: template_wamid match (strongest)
        if template_wamid:
            rid = (
                base_qs.filter(template_wamid=template_wamid)
                .values_list("event_registration", flat=True)
                .first()
            )
            if rid:
                er = EventRegistration.objects.get(pk=rid)

        # Priority 2: wa_id + event_id (campaign scoped)
        if not er and event_id:
            rid = (
                base_qs.filter(event_id=event_id)
                .order_by("-created_at")
                .values_list("event_registration", flat=True)
                .first()
            )
            if rid:
                er = EventRegistration.objects.get(pk=rid)

        # Priority 3: latest mapping for this wa_id (fallback)
        if not er:
            rid = (
                base_qs.order_by("-created_at")
                .values_list("event_registration", flat=True)
                .first()
            )
            if rid:
                er = EventRegistration.objects.get(pk=rid)

        if not er:
            return HttpResponseBadRequest("no mapping found for wa_id")

    # Update RSVP with normalized status (title case)
    er.rsvp_status = normalized_status  # "Maybe" instead of "maybe"
    er.responded_on = responded_on
    er.save(update_fields=["rsvp_status", "responded_on"])

    log.info(f"Updated RSVP status to '{normalized_status}' for registration {er.id}")

    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"event_{er.event_id}",
        {
            "type": "rsvp_update",  # consumer handler name
            "data": {
                "type": "rsvp_changed",  # <-- match your hook
                "action": "updated",
                "registration": {
                    "id": str(er.id),
                    "event": str(er.event_id),
                    "rsvp_status": er.rsvp_status,
                    "estimated_pax": getattr(er, "estimated_pax", None),
                    "additional_guest_count": getattr(
                        er, "additional_guest_count", None
                    ),
                    # include responded_on/updated_at if you want
                },
            },
        },
    )

    # Send immediate WhatsApp confirmation with next steps
    try:
        from MessageTemplates.services.whatsapp import send_choice_buttons, send_freeform_text
        
        event_name = er.event.name if er.event else "the event"
        
        if normalized_status == "Yes":
            # For "Yes" - send confirmation with travel details option
            message = (
                f"✅ Perfect! Your RSVP has been confirmed for {event_name}.\n\n"
                "We're looking forward to seeing you! 🎉\n\n"
                "What would you like to do next?"
            )
            buttons = [
                {
                    "id": f"tc|start_travel|{er.id}",
                    "title": "✈️ Provide Travel Details"
                },
                {
                    "id": f"tc|update_rsvp_menu|{er.id}",
                    "title": "🔄 Update RSVP"
                }
            ]
            send_choice_buttons(er.guest.phone, message, buttons)
            log.info(f"[RSVP] Sent post-RSVP options to {er.guest.phone}")
            
        elif normalized_status == "No":
            # For "No" - simple confirmation
            message = (
                f"Thank you for letting us know.\n\n"
                f"Your RSVP has been updated to: Not Attending ❌\n\n"
                "We hope to see you at future events!"
            )
            send_freeform_text(er.guest.phone, message)
            log.info(f"[RSVP] Sent decline confirmation to {er.guest.phone}")
            
        elif normalized_status == "Maybe":
            # For "Maybe" - simple confirmation
            message = (
                f"No problem! Your RSVP has been updated to: Maybe 🤔\n\n"
                "Please let us know when you decide!"
            )
            send_freeform_text(er.guest.phone, message)
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

    from Events.models.wa_send_map import WaSendMap
    from django.utils import timezone

    wa_digits = "".join(c for c in wa_id if c.isdigit())[-15:]

    row = (
        WaSendMap.objects.filter(wa_id=wa_digits, expires_at__gt=timezone.now())
        .order_by("-created_at")
        .values("event_id", "event_registration_id")
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
        }
    )
