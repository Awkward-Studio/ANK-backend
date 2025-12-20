from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseNotFound
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
import json
import logging

from Events.models.event_registration_model import EventRegistration

log = logging.getLogger(__name__)

@csrf_exempt
@require_http_methods(["GET"])
def resolve_opt_in_token(request, token):
    try:
        er = EventRegistration.objects.select_related('guest', 'event').get(whatsapp_opt_in_token=token)
    except EventRegistration.DoesNotExist:
        return HttpResponseNotFound("Invalid or expired token")

    guest = er.guest
    phone = guest.phone
    masked_phone = f"{phone[:3]} **** {phone[-3:]}" if len(phone) > 6 else phone

    return JsonResponse({
        "valid": True,
        "guest_name": guest.name,
        "phone_masked": masked_phone,
        "event_name": er.event.name,
        "status": er.whatsapp_opt_in_status,
    })

@csrf_exempt
@require_http_methods(["POST"])
def confirm_opt_in(request):
    try:
        body = json.loads(request.body)
        token = body.get("token")
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON")

    if not token:
        return HttpResponseBadRequest("Missing token")

    try:
        er = EventRegistration.objects.get(whatsapp_opt_in_token=token)
    except EventRegistration.DoesNotExist:
        return HttpResponseNotFound("Invalid token")

    er.whatsapp_opt_in_status = 'verified'
    er.whatsapp_opted_in_at = timezone.now()
    er.save(update_fields=['whatsapp_opt_in_status', 'whatsapp_opted_in_at'])

    return JsonResponse({"success": True})
