import json
import logging
import os
from datetime import datetime, timezone as tz

from django.conf import settings
from django.db.models import Q
from django.http import HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.utils import timezone as dj_tz
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.pagination import PageNumberPagination
from django.utils.dateparse import parse_datetime
from django.shortcuts import get_object_or_404

from Events.models.event_registration_model import EventRegistration
from Events.models.wa_send_map import WaSendMap
from Events.models.whatsapp_message_log import WhatsAppMessageLog
from Events.serializers.whatsapp_message_log_serializer import WhatsAppMessageLogSerializer
from MessageTemplates.models import FlowSession, FlowBlueprint
from MessageTemplates.services.flow_runner import FlowRunner

log = logging.getLogger("whatsapp_webhooks")

def _norm_digits(s):
    if not s: return ""
    return "".join(c for c in str(s) if c.isdigit())

def _ensure_aware(dt):
    if dt and dt.tzinfo is None:
        return dt.replace(tzinfo=tz.utc)
    return dt

def _get_header_token(request):
    return request.headers.get("X-Webhook-Token")

def _get_secret():
    return os.getenv("DJANGO_RSVP_SECRET")

@csrf_exempt
@require_http_methods(["POST"])
def whatsapp_rsvp(request):
    """
    Unified Inbound Webhook for WhatsApp.
    """
    token = _get_header_token(request)
    secret = _get_secret()
    if not secret or token != secret:
        return HttpResponseForbidden("invalid token")

    try:
        body = json.loads(request.body.decode("utf-8"))
    except Exception:
        return HttpResponseBadRequest("invalid json")

    raw_status = (body.get("rsvp_status") or body.get("body") or "").strip()
    wa_id_raw = body.get("wa_id", "")
    wa_digits = _norm_digits(wa_id_raw)
    
    # [FIX] Support both field names for sender number ID (Next.js vs Internal)
    to_phone_number_id = body.get("to_phone_number_id") or body.get("sender_phone_number_id")
    
    # [FIX] Support explicit WhatsApp Message ID (wamid) from Next.js proxy
    wamid = body.get("wamid") or body.get("wa_message_id")
    
    media_id = body.get("media_id")
    media_type = body.get("media_type")

    log.info(f"[WEBHOOK-IN] From: {wa_id_raw} | Text: '{raw_status}' | ToNumberID: {to_phone_number_id} | WAMID: {wamid}")

    # 1. Resolve Registration Context
    er = None
    reg_id = body.get("event_registration_id")
    if reg_id:
        er = EventRegistration.objects.filter(pk=reg_id).first()
    
    if not er and wa_digits:
        search_suffix = wa_digits[-10:]
        latest_map = WaSendMap.objects.filter(
            wa_id__endswith=search_suffix, 
            expires_at__gt=dj_tz.now()
        ).order_by("-created_at").first()
        
        if latest_map:
            er = latest_map.event_registration
            log.info(f"[WEBHOOK-RESOLVE] Found via WaSendMap: {er.id}")
        else:
            er = EventRegistration.objects.filter(
                guest__phone__endswith=search_suffix
            ).order_by("-created_at").first()
            if er: log.info(f"[WEBHOOK-RESOLVE] Found via Guest Phone endswith: {er.id}")

    if not er:
        log.warning(f"[WEBHOOK] Could not resolve registration for phone suffix {wa_digits[-10:]}")
        return JsonResponse({"ok": True, "resolved": False})

    # 2. PRIORITY: Delegate to Active Visual Flow
    waiting_flow_session = FlowSession.objects.filter(registration=er, status='WAITING_FOR_INPUT').order_by("-last_interaction").first()
    
    button_id = body.get("button_id") or ""
    is_flow_button = button_id.startswith("flow|")
    is_reset_cmd = raw_status.lower().strip() in {"restart", "stop", "unsubscribe"}
    
    if waiting_flow_session and (is_flow_button or not is_reset_cmd):
        try:
            flow_input = button_id or raw_status
            log.info(f"[WEBHOOK-FLOW] Delegating '{flow_input}' to Flow {waiting_flow_session.flow.name}")
            runner = FlowRunner(waiting_flow_session, sender_phone_number_id=to_phone_number_id)
            
            payload_type = "interactive" if bool(button_id) else "text"
            error_reply, is_done = runner.process_input(flow_input, payload_type=payload_type)
            
            if error_reply:
                from Events.services.message_logger import MessageLogger
                MessageLogger.send_text(er, error_reply, "flow", phone_number_id=to_phone_number_id)
            
            return JsonResponse({"ok": True, "delegated_flow": True, "done": is_done})
        except Exception as e:
            log.exception(f"[WEBHOOK-FLOW] Execution Failed: {e}")

    # 3. Handle STOP / Unsubscribe
    if raw_status.lower().strip() in {"stop", "unsubscribe"}:
         er.whatsapp_opt_in_status = 'opt_out'
         er.save(update_fields=['whatsapp_opt_in_status'])
         from MessageTemplates.services.whatsapp import send_freeform_text
         try: send_freeform_text(wa_id_raw, "You have been unsubscribed from updates.", phone_number_id=to_phone_number_id)
         except: pass
         return JsonResponse({"ok": True, "status": "opt_out"})

    # 4. START FLOW BY KEYWORD
    blueprint = FlowBlueprint.objects.filter(trigger_keyword__iexact=raw_status, is_active=True).first()
    if blueprint:
        log.info(f"[WEBHOOK-KEYWORD] Starting Flow {blueprint.name} for reg {er.id}")
        FlowSession.objects.filter(registration=er, flow=blueprint).delete()
        session = FlowSession.objects.create(registration=er, flow=blueprint, status='RUNNING')
        runner = FlowRunner(session, sender_phone_number_id=to_phone_number_id)
        runner.start()
        return JsonResponse({"ok": True, "flow_started": blueprint.name})

    # 5. Log as general interaction
    from Events.services.message_logger import MessageLogger
    MessageLogger.log_inbound(
        event_registration=er,
        content=raw_status,
        message_type="custom",
        wa_message_id=wamid or wa_id_raw or "no_wamid",
        media_id=media_id,
        media_type=media_type,
        metadata=body,
        sender_phone_number_id=to_phone_number_id,
    )

    try: WaSendMap.objects.filter(wa_id__endswith=wa_digits[-10:]).update(consumed_at=dj_tz.now())
    except: pass

    return JsonResponse({"ok": True})

@csrf_exempt
@require_http_methods(["POST"])
def track_send(request):
    """
    Creates a WaSendMap entry to ensure inbound replies are correctly routed.
    """
    token = _get_header_token(request)
    secret = _get_secret()
    if not secret or token != secret: return HttpResponseForbidden("invalid token")

    try: body = json.loads(request.body.decode("utf-8"))
    except: return HttpResponseBadRequest("invalid json")

    wa_id = _norm_digits(body.get("wa_id", ""))
    template_wamid = body.get("template_wamid")
    event_registration_id = body.get("event_registration_id")
    sender_phone_number_id = body.get("sender_phone_number_id")
    flow_type = body.get("flow_type")

    try:
        from datetime import timedelta
        er = EventRegistration.objects.get(pk=event_registration_id)
        WaSendMap.objects.update_or_create(
            template_wamid=template_wamid,
            defaults={
                "wa_id": wa_id,
                "event_registration": er,
                "event_id": er.event_id,
                "sender_phone_number_id": sender_phone_number_id,
                "flow_type": flow_type,
                "expires_at": dj_tz.now() + timedelta(days=4),
            }
        )
        return JsonResponse({"ok": True})
    except: return JsonResponse({"ok": False}, status=400)

@csrf_exempt
@require_http_methods(["GET"])
def resolve_wa(request, wa_id):
    token = request.headers.get("X-Webhook-Token", "")
    if token != os.getenv("DJANGO_RSVP_SECRET"):
        return JsonResponse({"ok": False, "error": "forbidden"}, status=403)

    wa_digits = _norm_digits(wa_id)
    sender_phone_number_id = request.GET.get("sender_phone_number_id")

    qs = WaSendMap.objects.filter(wa_id__endswith=wa_digits[-10:], expires_at__gt=dj_tz.now())
    if sender_phone_number_id:
        qs = qs.filter(sender_phone_number_id=sender_phone_number_id)

    row = qs.order_by("-created_at").values("event_id", "event_registration_id", "flow_type").first()
    if not row: return JsonResponse({"ok": False, "found": False})

    return JsonResponse({
        "ok": True,
        "found": True,
        "event_id": row["event_id"],
        "registration_id": row["event_registration_id"],
        "flow_type": row.get("flow_type"),
    })

@csrf_exempt
@require_http_methods(["POST"])
def message_status_webhook(request):
    token = _get_header_token(request)
    secret = _get_secret()
    if not secret or token != secret: return HttpResponseForbidden("invalid token")

    try: body = json.loads(request.body.decode("utf-8"))
    except: return HttpResponseBadRequest("invalid json")

    wamid = body.get("wamid")
    status = body.get("status")
    recipient_id = _norm_digits(body.get("recipient_id", ""))
    errors = body.get("errors")

    msg_log, _ = WhatsAppMessageLog.objects.get_or_create(wamid=wamid, defaults={"recipient_id": recipient_id, "status": status})
    
    status_order = {"sent": 1, "delivered": 2, "read": 3, "failed": 0}
    if status_order.get(status, 0) > status_order.get(msg_log.status, 0) or status == "failed":
        msg_log.status = status
        if status == "failed" and errors:
            msg_log.error_code = str(errors[0].get("code", ""))
            msg_log.error_message = errors[0].get("title", "")
        msg_log.save()

    return JsonResponse({"ok": True, "status": msg_log.status})

@csrf_exempt
@require_http_methods(["POST"])
def message_status_lookup(request):
    token = _get_header_token(request)
    secret = _get_secret()
    if not secret or token != secret: return HttpResponseForbidden("invalid token")

    try: body = json.loads(request.body.decode("utf-8"))
    except: return HttpResponseBadRequest("invalid json")

    wamids = body.get("wamids", [])
    logs = WhatsAppMessageLog.objects.filter(wamid__in=wamids)
    statuses = {msg_log.wamid: {"status": msg_log.status, "error": msg_log.error_message} for msg_log in logs}
    return JsonResponse({"statuses": statuses})

@api_view(["GET"])
@permission_classes([AllowAny])
def message_logs(request):
    token = _get_header_token(request)
    secret = _get_secret()
    if not secret or token != secret: return JsonResponse({"detail": "Invalid token"}, status=403)

    queryset = WhatsAppMessageLog.objects.all().order_by("-sent_at")
    rid = request.GET.get("registration_id")
    if rid: queryset = queryset.filter(event_registration_id=rid)
    
    paginator = PageNumberPagination()
    paginator.page_size = int(request.GET.get("limit", 20))
    result_page = paginator.paginate_queryset(queryset, request)
    serializer = WhatsAppMessageLogSerializer(result_page, many=True)
    return paginator.get_paginated_response(serializer.data)

@csrf_exempt
@require_http_methods(["GET"])
def message_logs_latest(request):
    token = _get_header_token(request)
    secret = _get_secret()
    if not secret or token != secret: return HttpResponseForbidden("invalid token")

    registration_id = request.GET.get("registration_id")
    msg_log = WhatsAppMessageLog.objects.filter(event_registration_id=registration_id).order_by("-sent_at").first()
    if not msg_log: return JsonResponse({"log": None})

    return JsonResponse({
        "log": {
            "id": str(msg_log.id),
            "wamid": msg_log.wamid,
            "status": msg_log.status,
            "sent_at": msg_log.sent_at.isoformat() if msg_log.sent_at else None,
            "error_message": msg_log.error_message,
        }
    })
