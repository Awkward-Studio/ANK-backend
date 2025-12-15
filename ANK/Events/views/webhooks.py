import json
import logging
import os
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

    log.info(
        "track_send body=%s wa_id=%s event_id=%s reg_id=%s flow_type=%s",
        body,
        wa_id,
        event_id,
        reg_id,
        flow_type,
    )

    if not wa_id:
        return HttpResponseBadRequest("missing wa_id")

    # Check if this is a standalone message (no event/registration context)
    # This supports bulk-send and other template messages sent outside event flows
    is_standalone = not event_id and not reg_id

    if is_standalone:
        # For standalone messages, only create WhatsAppMessageLog (no WaSendMap)
        if not template_wamid:
            return HttpResponseBadRequest(
                "missing template_wamid for standalone message"
            )

        try:
            template_name = body.get("template_name")
            guest_name = body.get("guest_name")

            WhatsAppMessageLog.objects.update_or_create(
                wamid=template_wamid,
                defaults={
                    "recipient_id": wa_id,
                    "status": "sent",
                    "sent_at": dj_tz.now(),
                    "event_registration_id": None,
                    "event_id": None,
                    "template_name": template_name,
                    "flow_type": flow_type or "standalone",
                    "message_type": message_type or "template",
                    "guest_id": None,
                    "guest_name": guest_name,
                },
            )
            log.info(
                f"[TRACK-SEND][STANDALONE] Created message log for wamid={template_wamid[:30]}..."
            )
        except Exception as log_err:
            log.warning(
                f"[TRACK-SEND][STANDALONE] Failed to create message log: {log_err}"
            )
            return JsonResponse({"ok": False, "error": str(log_err)}, status=500)

        return JsonResponse({"ok": True, "standalone": True, "wamid": template_wamid})

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
            "expires_at": dj_tz.now() + timedelta(days=30),
            "flow_type": flow_type,
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
                # (wa_id, event_registration, flow_type, template_wamid=NULL)
                obj, _ = WaSendMap.objects.update_or_create(
                    wa_id=wa_id,
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
                    "guest_id": str(guest_id) if guest_id else None,
                    "guest_name": guest_name,
                },
            )
            log.info(
                f"[TRACK-SEND] Created message log for wamid={template_wamid[:30]}..."
            )
        except Exception as log_err:
            # Non-fatal - don't fail the request if logging fails
            log.warning(f"[TRACK-SEND] Failed to create message log: {log_err}")

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
        "yes": "Yes",
        "no": "No",
        "maybe": "Maybe",
        "pending": "Pending",
        "not_sent": "Not_Sent",
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
        flow_type_expected = "rsvp"

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
                base_qs.filter(event_id=event_id, flow_type=flow_type_expected)
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
            # STANDALONE / UNREGISTERED MESSAGE HANDLING
            # If we cannot resolve a registration, we still want to log this message
            # so it appears in the Bulk Chat History (standalone view).
            
            # Create a log entry for this unknown inbound message
            from Events.models.whatsapp_message_log import WhatsAppMessageLog
            
            WhatsAppMessageLog.objects.create(
                wamid=body.get("wa_id", "") or f"unknown-{dj_tz.now().timestamp()}",
                recipient_id=wa_id,
                status="received",
                sent_at=responded_on,
                direction="inbound",
                body=f"RSVP: {raw_status}" if raw_status else "Unknown text",
                message_type="custom",
                flow_type="standalone",
            )
            
            log.info(f"[WEBHOOK] Logged standalone inbound message from {wa_id}")
            return JsonResponse({"ok": True, "standalone": True})
            
            # Old behavior: return HttpResponseBadRequest("no mapping found for wa_id")

    # Update RSVP with normalized status (title case)
    er.rsvp_status = normalized_status  # "Maybe" instead of "maybe"
    # er.responded_on is updated via MessageLogger
    er.save(update_fields=["rsvp_status"])

    # Log inbound message
    from Events.services.message_logger import MessageLogger

    MessageLogger.log_inbound(
        event_registration=er,
        content=f"RSVP: {normalized_status}",
        message_type="rsvp",
        wa_message_id=body.get("wa_id", ""),  # Best effort if available here
        metadata=body,
    )

    log.info(f"Updated RSVP status to '{normalized_status}' for registration {er.id}")

    # Send immediate WhatsApp confirmation with next steps
    try:
        from Events.services.message_logger import MessageLogger as MsgLogger

        event_name = er.event.name if er.event else "the event"

        if normalized_status == "Yes":
            # For "Yes" - send confirmation with travel details option
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


@csrf_exempt
@require_http_methods(["GET"])
def message_logs(request):
    """
    Get message logs filtered by registration, event, guest, or recipient phone.

    GET /api/webhooks/message-logs/
    Query params:
        - registration_id: Filter by registration
        - event_id: Filter by event
        - guest_id: Filter by guest
        - recipient_id: Filter by recipient phone number (for standalone messages)
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
        return HttpResponseForbidden("invalid token")

    registration_id = request.GET.get("registration_id")
    event_id = request.GET.get("event_id")
    guest_id = request.GET.get("guest_id")
    recipient_id = request.GET.get("recipient_id")
    template_name = request.GET.get("template_name")
    standalone_only = request.GET.get("standalone", "").lower() == "true"

    queryset = WhatsAppMessageLog.objects.all()

    if registration_id:
        queryset = queryset.filter(event_registration_id=registration_id)
    if event_id:
        queryset = queryset.filter(event_id=event_id)
    if guest_id:
        queryset = queryset.filter(guest_id=guest_id)
    if recipient_id:
        # Normalize phone number (keep last 10-15 digits)
        normalized = _norm_digits(recipient_id)
        queryset = queryset.filter(recipient_id__endswith=normalized[-10:])
    if template_name:
        queryset = queryset.filter(template_name=template_name)
    if standalone_only:
        queryset = queryset.filter(
            event_id__isnull=True, event_registration_id__isnull=True
        )

    # Limit to 50 most recent
    queryset = queryset.order_by("-sent_at")[:50]

    logs = []
    for msg_log in queryset:
        logs.append(
            {
                "id": str(msg_log.id),
                "wamid": msg_log.wamid,
                "recipient_id": msg_log.recipient_id,
                "status": msg_log.status,
                "message_type": msg_log.message_type,
                "template_name": msg_log.template_name,
                "event_id": msg_log.event_id,
                "registration_id": msg_log.event_registration_id,
                "guest_id": msg_log.guest_id,
                "guest_name": msg_log.guest_name,
                "sent_at": msg_log.sent_at.isoformat() if msg_log.sent_at else None,
                "delivered_at": msg_log.delivered_at.isoformat()
                if msg_log.delivered_at
                else None,
                "read_at": msg_log.read_at.isoformat() if msg_log.read_at else None,
                "failed_at": msg_log.failed_at.isoformat()
                if msg_log.failed_at
                else None,
                "error_code": msg_log.error_code,
                "error_message": msg_log.error_message,
                "direction": msg_log.direction,
                "body": msg_log.body,
            }
        )

    return JsonResponse({"logs": logs})


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
