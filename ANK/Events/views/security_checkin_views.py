import json
import logging
import re
import hashlib
import hmac
from django.conf import settings
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from Events.models.event_model import Event
from Events.models.event_registration_model import EventRegistration
from Events.models.session_model import Session
from Events.models.session_registration import SessionRegistration
from Events.models.wa_send_map import WaSendMap
from Guest.models import Guest
from MessageTemplates.temporary_tools.qr_test_media import decrypt_security_qr_payload
from MessageTemplates.models import QrScanEvent, QrTicket

logger = logging.getLogger("security_checkin")

ALLOWED_SECURITY_ROLES = {"security", "admin", "super_admin"}


def _record_qr_scan(token, action, actor=None, event=None, session_registration=None, error_message=""):
    digest = hashlib.sha256(str(token).encode("utf-8")).hexdigest()
    ticket = QrTicket.objects.filter(token_digest=digest).first()
    if ticket:
        QrTicket.objects.filter(pk=ticket.pk).update(
            scan_count=F("scan_count") + 1,
            last_scanned_at=timezone.now(),
        )
    QrScanEvent.objects.create(
        ticket=ticket,
        token_digest=digest,
        action=action,
        event=event,
        session_registration=session_registration,
        security_user=actor if getattr(actor, "is_authenticated", False) else None,
        error_message=error_message,
    )


def check_security_access(request):
    """
    Check if the request is authorized to perform security verification and check-ins.
    Supports:
    1. Authenticated Django user with allowed role (security, admin, super_admin)
    2. Server-to-server webhook token (X-Webhook-Token: DJANGO_RSVP_SECRET)
       with authorized X-User-Role header or fallback.
    """
    # 1. Server-to-server secret authentication
    expected_secret = getattr(settings, "DJANGO_RSVP_SECRET", "")
    supplied_secret = request.headers.get("X-Webhook-Token") or request.headers.get("x-webhook-token")
    secret_matches = bool(
        expected_secret
        and supplied_secret
        and hmac.compare_digest(str(supplied_secret), str(expected_secret))
    )
    user_role = (
        request.headers.get("X-User-Role")
        or request.headers.get("x-user-role")
        or "security"
    ).strip().lower()
    logger.info(
        "[SecurityAccess] webhook authorization configured=%s supplied=%s matches=%s role=%s",
        bool(expected_secret),
        bool(supplied_secret),
        secret_matches,
        user_role,
    )
    if secret_matches:
        if user_role in ALLOWED_SECURITY_ROLES:
            return True, None, user_role, status.HTTP_200_OK

    # 2. Standard DRF / Django authentication
    user = getattr(request, "user", None)
    if user and user.is_authenticated:
        role = getattr(user, "role", None)
        if role in ALLOWED_SECURITY_ROLES:
            return True, user, role, status.HTTP_200_OK
        return False, None, f"Forbidden: Role '{role}' is not authorized for security operations.", status.HTTP_403_FORBIDDEN

    return False, None, "Authentication required. Only security personnel can access this module.", status.HTTP_401_UNAUTHORIZED


def normalize_phone_digits(phone_str: str) -> str:
    """Strip all non-digit characters from phone number."""
    if not phone_str:
        return ""
    return re.sub(r"\D", "", str(phone_str))


def resolve_guest_registration(payload, target_session_id=None):
    """
    Resolves the EventRegistration and optional SessionRegistration from a decrypted QR payload.
    Supports:
    - Explicit registration_id or event_registration_id
    - Explicit session_registration_id
    - UID + event_id
    - guest_id + event_id
    - session_id + guest_id
    - test_id matching EventRegistration.id or WaSendMap
    - phone number matching Guest in database
    """
    if not isinstance(payload, dict):
        return None, None

    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}

    # First resolve the persisted ticket identity. The ticket binding is authoritative;
    # never let an embedded registration field override it if they diverge.
    ticket_id = payload.get("qr_ticket_id") or payload.get("ticket_id")
    if ticket_id:
        try:
            ticket = QrTicket.objects.select_related(
                "event_registration", "session_registration", "event"
            ).filter(id=ticket_id).first()
            if ticket:
                # A generated ticket must be bound to a registration before it
                # can be used for admission; do not fall back to phone matching.
                if ticket.event_registration:
                    return ticket.event_registration, ticket.session_registration
                return None, None
        except Exception:
            pass

    # Strategy 1: Explicit registration_id / event_registration_id
    reg_id = (
        payload.get("registration_id")
        or payload.get("event_registration_id")
        or data.get("registration_id")
        or data.get("event_registration_id")
    )
    if reg_id:
        try:
            reg = EventRegistration.objects.select_related("guest", "event").filter(id=reg_id).first()
            if reg:
                sreg = None
                if target_session_id:
                    sreg = SessionRegistration.objects.select_related("session", "guest").filter(
                        guest=reg.guest, session_id=target_session_id
                    ).first()
                return reg, sreg
        except Exception:
            pass

    # Strategy 2: Explicit session_registration_id
    session_reg_id = payload.get("session_registration_id") or data.get("session_registration_id")
    if session_reg_id:
        try:
            sreg = SessionRegistration.objects.select_related("guest", "session", "session__event").filter(
                id=session_reg_id
            ).first()
            if sreg:
                event_reg = EventRegistration.objects.select_related("guest", "event").filter(
                    guest=sreg.guest, event=sreg.session.event
                ).first()
                return event_reg, sreg
        except Exception:
            pass

    # Strategy 3: UID + event_id
    uid = payload.get("uid") or data.get("uid")
    event_id = payload.get("event_id") or data.get("event_id")
    if uid and event_id:
        try:
            reg = EventRegistration.objects.select_related("guest", "event").filter(
                event_id=event_id, uid=uid
            ).first()
            if reg:
                sreg = None
                if target_session_id:
                    sreg = SessionRegistration.objects.select_related("session", "guest").filter(
                        guest=reg.guest, session_id=target_session_id
                    ).first()
                return reg, sreg
        except Exception:
            pass

    # Strategy 4: guest_id + event_id
    guest_id = payload.get("guest_id") or data.get("guest_id")
    if guest_id and event_id:
        try:
            reg = EventRegistration.objects.select_related("guest", "event").filter(
                event_id=event_id, guest_id=guest_id
            ).first()
            if reg:
                sreg = None
                if target_session_id:
                    sreg = SessionRegistration.objects.select_related("session", "guest").filter(
                        guest=reg.guest, session_id=target_session_id
                    ).first()
                return reg, sreg
        except Exception:
            pass

    # Strategy 5: session_id + guest_id
    session_id = payload.get("session_id") or data.get("session_id") or target_session_id
    if session_id and guest_id:
        try:
            sreg = SessionRegistration.objects.select_related("guest", "session", "session__event").filter(
                session_id=session_id, guest_id=guest_id
            ).first()
            if sreg:
                event_reg = EventRegistration.objects.select_related("guest", "event").filter(
                    guest=sreg.guest, event=sreg.session.event
                ).first()
                return event_reg, sreg
        except Exception:
            pass

    # Strategy 6: test_id matching EventRegistration.id or WaSendMap
    test_id = payload.get("test_id")
    if test_id:
        try:
            reg = EventRegistration.objects.select_related("guest", "event").filter(id=test_id).first()
            if reg:
                return reg, None
            send_map = WaSendMap.objects.select_related(
                "event_registration", "event_registration__guest", "event_registration__event"
            ).filter(template_wamid=test_id).first()
            if send_map and send_map.event_registration:
                return send_map.event_registration, None
        except Exception:
            pass

    # Strategy 7: Phone number lookup
    recipient = payload.get("recipient") if isinstance(payload.get("recipient"), dict) else {}
    phone = recipient.get("phone") or payload.get("phone") or data.get("phone")
    if phone:
        phone_digits = normalize_phone_digits(phone)
        guest = None
        if phone_digits:
            guest = Guest.objects.filter(phone=phone).first()
            if not guest and len(phone_digits) >= 10:
                guest = Guest.objects.filter(phone__endswith=phone_digits[-10:]).first()
            if not guest:
                guest = Guest.objects.filter(Q(phone=f"+{phone_digits}") | Q(phone=phone_digits)).first()

        if guest:
            # If event_id is specified
            if event_id:
                reg = EventRegistration.objects.select_related("guest", "event").filter(
                    guest=guest, event_id=event_id
                ).first()
                if reg:
                    return reg, None
            # Otherwise latest event registration
            reg = EventRegistration.objects.select_related("guest", "event").filter(
                guest=guest
            ).order_by("-created_at").first()
            if reg:
                return reg, None

    return None, None


class SecurityVerifyPassAPIView(APIView):
    """
    POST /api/events/security/verify-pass/
    Decrypts a security QR pass and retrieves full guest, event, session,
    and attendance verification details from the database.
    """
    # Authentication is performed by check_security_access below. Without
    # AllowAny, the global IsAuthenticated permission rejects webhook-token
    # requests before this view can validate X-Webhook-Token.
    permission_classes = [AllowAny]

    def post(self, request):
        is_auth, actor, err_or_role, auth_status = check_security_access(request)
        if not is_auth:
            return Response({"ok": False, "valid": False, "error": err_or_role}, status=auth_status)

        token = str(request.data.get("token") or request.data.get("qr_text") or "").strip()
        target_session_id = request.data.get("session_id")

        if not token:
            return Response({"ok": False, "valid": False, "error": "QR token is required."}, status=status.HTTP_400_BAD_REQUEST)

        # 1. Decrypt QR pass using AES-256-GCM
        try:
            payload = decrypt_security_qr_payload(token)
        except Exception as exc:
            logger.warning("[SecurityVerifyPass] Failed to decrypt token: %s", exc)
            _record_qr_scan(token, "rejected", actor, error_message="Corrupted, tampered, or forged QR pass.")
            return Response(
                {
                    "ok": True,
                    "valid": False,
                    "error": "Pass verification failed: Corrupted, tampered, or forged QR pass.",
                },
                status=status.HTTP_200_OK,
            )

        target_session_id = target_session_id or payload.get("session_id")

        # 2. Resolve guest and registration in database
        event_reg, session_reg = resolve_guest_registration(payload, target_session_id)

        if not event_reg:
            # Valid crypto token but no matching database guest registration
            _record_qr_scan(token, "rejected", actor, error_message="No matching guest registration found in database.")
            return Response(
                {
                    "ok": True,
                    "valid": False,
                    "payload": payload,
                    "error": "No matching guest registration found in database for this pass.",
                },
                status=status.HTTP_200_OK,
            )

        _record_qr_scan(token, "verified", actor, event=event_reg.event, session_registration=session_reg)

        guest = event_reg.guest
        event = event_reg.event

        # 3. Retrieve all session registrations for this guest in this event
        session_regs = SessionRegistration.objects.select_related("session").filter(
            guest=guest, session__event=event
        ).order_by("session__start_time")

        all_sessions = []
        for s in session_regs:
            all_sessions.append({
                "id": str(s.session.id),
                "title": s.session.title,
                "venue_name": s.session.venue_name or s.session.location or "",
                "date": s.session.date.isoformat() if s.session.date else None,
                "start_time": s.session.start_time.isoformat() if s.session.start_time else None,
                "end_time": s.session.end_time.isoformat() if s.session.end_time else None,
                "is_checked_in": s.is_checked_in,
                "checked_in_at": s.checked_in_at.isoformat() if s.checked_in_at else None,
                "check_in_count": s.session.check_in_count,
            })

        # 4. Determine overall attendance status
        # If target session specified, use session's status; otherwise use event registration status
        is_already_checked_in = session_reg.is_checked_in if session_reg else event_reg.is_checked_in
        check_in_time = session_reg.checked_in_at if session_reg else event_reg.checked_in_at

        # 5. Build full guest and registration response
        response_data = {
            "ok": True,
            "valid": True,
            "already_checked_in": is_already_checked_in,
            "checked_in_at": check_in_time.isoformat() if check_in_time else None,
            "payload": payload,
            "guest": {
                "id": str(guest.id),
                "name": guest.name,
                "email": guest.email or "",
                "phone": guest.phone or "",
                "city": guest.city or "",
                "nationality": guest.nationality or "",
                "address": guest.address or "",
            },
            "event": {
                "id": str(event.id),
                "name": event.name,
                "type": event.type,
                "venue": event.venue or "",
                "location": event.location or "",
                "start_date": event.start_date.isoformat() if event.start_date else None,
                "end_date": event.end_date.isoformat() if event.end_date else None,
                "bride_name": event.bride_name or "",
                "groom_name": event.groom_name or "",
                "check_in_count": event.check_in_count,
            },
            "session": {
                "id": str(session_reg.session.id),
                "title": session_reg.session.title,
                "venue_name": session_reg.session.venue_name or session_reg.session.location or "",
                "date": session_reg.session.date.isoformat() if session_reg.session.date else None,
                "start_time": session_reg.session.start_time.isoformat() if session_reg.session.start_time else None,
                "end_time": session_reg.session.end_time.isoformat() if session_reg.session.end_time else None,
                "is_checked_in": session_reg.is_checked_in,
                "checked_in_at": session_reg.checked_in_at.isoformat() if session_reg.checked_in_at else None,
                "check_in_count": session_reg.session.check_in_count,
            } if session_reg else None,
            "registration": {
                "id": str(event_reg.id),
                "uid": event_reg.uid or "",
                "rsvp_status": event_reg.rsvp_status,
                "guest_group": event_reg.guest_group or "",
                "sub_guest_group": event_reg.sub_guest_group or "",
                "family_salutation": event_reg.family_salutation or "",
                "name_on_message": event_reg.name_on_message or "",
                "title": event_reg.title or "",
                "estimated_pax": event_reg.estimated_pax or 1,
                "additional_guest_count": event_reg.additional_guest_count or 0,
                "hamper_count": event_reg.hamper_count or 0,
                "is_checked_in": event_reg.is_checked_in,
                "checked_in_at": event_reg.checked_in_at.isoformat() if event_reg.checked_in_at else None,
            },
            "all_sessions": all_sessions,
            "verified_at": timezone.now().isoformat(),
        }

        return Response(response_data, status=status.HTTP_200_OK)


class SecurityCheckInAPIView(APIView):
    """
    POST /api/events/security/check-in/
    Marks a guest as checked in.
    - Validates QR token on backend against database (never blindly trusts frontend ID).
    - Ensures check-in is atomic and concurrency-safe via select_for_update().
    - Prevents duplicate check-in (returns 409 Conflict if already checked in).
    - Tracks check-in timestamp and verifying security officer.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        is_auth, actor, err_or_role, auth_status = check_security_access(request)
        if not is_auth:
            return Response({"ok": False, "error": err_or_role}, status=auth_status)

        token = str(request.data.get("token") or "").strip()
        supplied_registration_id = request.data.get("registration_id")
        target_session_id = request.data.get("session_id")

        if not token:
            return Response({"ok": False, "error": "Security QR token is required."}, status=status.HTTP_400_BAD_REQUEST)

        # 1. Decrypt and verify pass token
        try:
            payload = decrypt_security_qr_payload(token)
        except Exception as exc:
            logger.warning("[SecurityCheckIn] Decryption failure: %s", exc)
            _record_qr_scan(token, "rejected", actor, error_message="Invalid or tampered security pass.")
            return Response({"ok": False, "error": "Invalid or tampered security pass."}, status=status.HTTP_400_BAD_REQUEST)

        # 2. Resolve guest and event registration directly from verified QR payload
        resolved_event_reg, resolved_session_reg = resolve_guest_registration(payload, target_session_id)
        if not resolved_event_reg:
            _record_qr_scan(token, "rejected", actor, error_message="Legitimate guest registration not found.")
            return Response({"ok": False, "error": "Legitimate guest registration not found for this pass."}, status=status.HTTP_404_NOT_FOUND)

        # 3. Security cross-validation: Do not trust frontend registration ID if it mismatches
        if supplied_registration_id and str(resolved_event_reg.id) != str(supplied_registration_id):
            logger.warning(
                "[SecurityCheckIn] Tampering detected: Supplied registration ID %s does not match token %s",
                supplied_registration_id, resolved_event_reg.id
            )
            return Response(
                {"ok": False, "error": "Security validation failed: Registration mismatch between token and request."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        target_session_id = target_session_id or payload.get("session_id")
        if not target_session_id and resolved_session_reg:
            target_session_id = str(resolved_session_reg.session_id)

        # 4. If session_id supplied, verify session belongs to registration's event
        target_session = None
        if target_session_id:
            target_session = Session.objects.filter(id=target_session_id, event=resolved_event_reg.event).first()
            if not target_session:
                return Response(
                    {"ok": False, "error": "Selected function does not belong to this guest's event."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        now = timezone.now()
        officer_user = actor if (actor and hasattr(actor, "is_authenticated") and actor.is_authenticated) else None

        # 5. Concurrency-safe atomic check-in with row-level locking
        try:
            with transaction.atomic():
                # Lock the event registration row to prevent concurrent race condition
                reg = EventRegistration.objects.select_for_update().get(id=resolved_event_reg.id)

                sreg = None
                if target_session:
                    sreg = SessionRegistration.objects.select_for_update().filter(
                        guest=reg.guest, session=target_session
                    ).first()
                    if not sreg:
                        return Response(
                            {"ok": False, "error": f"Guest {reg.guest.name} is not registered for '{target_session.title}'."},
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                    # Check duplicate for function
                    if sreg.is_checked_in:
                        _record_qr_scan(
                            token, "duplicate", actor, event=reg.event,
                            session_registration=sreg,
                            error_message=f"Guest has already checked in to {target_session.title}.",
                        )
                        return Response(
                            {
                                "ok": False,
                                "already_checked_in": True,
                                "error": f"Guest has already checked in to {target_session.title}.",
                                "checked_in_at": sreg.checked_in_at.isoformat() if sreg.checked_in_at else None,
                                "function_name": target_session.title,
                            },
                            status=status.HTTP_409_CONFLICT,
                        )

                # Check duplicate for event level (when no specific session or general check-in)
                if not target_session and reg.is_checked_in:
                    _record_qr_scan(
                        token, "duplicate", actor, event=reg.event,
                        error_message="Guest has already checked in.",
                    )
                    return Response(
                        {
                            "ok": False,
                            "already_checked_in": True,
                            "error": "Guest has already checked in.",
                            "checked_in_at": reg.checked_in_at.isoformat() if reg.checked_in_at else None,
                        },
                        status=status.HTTP_409_CONFLICT,
                    )

                # Mark event registration attended
                if not reg.is_checked_in:
                    reg.is_checked_in = True
                    reg.checked_in_at = now
                    if officer_user:
                        reg.checked_in_by = officer_user
                    reg.save(update_fields=["is_checked_in", "checked_in_at", "checked_in_by"])
                    Event.objects.filter(pk=reg.event_id).update(check_in_count=F("check_in_count") + 1)

                # Mark session registration attended if applicable
                if sreg:
                    sreg.is_checked_in = True
                    sreg.checked_in_at = now
                    if officer_user:
                        sreg.checked_in_by = officer_user
                    sreg.save(update_fields=["is_checked_in", "checked_in_at", "checked_in_by"])
                    Session.objects.filter(pk=sreg.session_id).update(check_in_count=F("check_in_count") + 1)

        except Exception as exc:
            logger.exception("[SecurityCheckIn] Database check-in error: %s", exc)
            return Response({"ok": False, "error": "Internal error processing check-in."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        _record_qr_scan(token, "checked_in", actor, event=reg.event, session_registration=sreg)

        return Response(
            {
                "ok": True,
                "success": True,
                "message": f"Guest {reg.guest.name} successfully checked in.",
                "checked_in_at": now.isoformat(),
                "guest_name": reg.guest.name,
                "event_name": reg.event.name,
                "function_name": target_session.title if target_session else None,
                "is_checked_in": True,
                "event_check_in_count": Event.objects.filter(pk=reg.event_id).values_list("check_in_count", flat=True).first(),
                "session_check_in_count": Session.objects.filter(pk=target_session.id).values_list("check_in_count", flat=True).first() if target_session else None,
            },
            status=status.HTTP_200_OK,
        )
