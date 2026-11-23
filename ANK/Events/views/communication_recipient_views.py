import re

from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from Departments.permissions import PermissionChecker
from Events.models.event_model import Event
from Events.models.event_registration_model import EventRegistration
from Events.models.session_model import Session
from Events.models.session_registration import SessionRegistration
from Guest.models import Guest


def normalize_whatsapp_phone(value):
    """Return the canonical WhatsApp number used by the communications UI."""
    raw = str(value or "").strip()
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 10:
        digits = f"91{digits}"
    if len(digits) < 11 or len(digits) > 15:
        raise ValueError("Enter a valid WhatsApp number including the country code.")
    return f"+{digits}"


def find_guest_by_phone(phone, event):
    """Prefer an existing event guest, while tolerating legacy phone formatting."""
    normalized = normalize_whatsapp_phone(phone)
    exact = list(Guest.objects.filter(phone=normalized))

    # Legacy rows may contain spaces, brackets, or dashes. Narrow the database
    # lookup with the final digits, then compare canonical values in Python.
    if not exact:
        digits = normalized[1:]
        suffix = digits[-7:]
        pattern = r"\D*".join(re.escape(char) for char in suffix) + r"\D*$"
        candidates = Guest.objects.filter(phone__regex=pattern)
        exact = [
            guest
            for guest in candidates
            if _phones_match(guest.phone, normalized)
        ]

    if not exact:
        return None

    existing_registration = (
        EventRegistration.objects.filter(event=event, guest__in=exact)
        .select_related("guest")
        .first()
    )
    return existing_registration.guest if existing_registration else exact[0]


def _phones_match(left, right):
    try:
        return normalize_whatsapp_phone(left) == normalize_whatsapp_phone(right)
    except ValueError:
        return False


class CommunicationRecipientRegistrationAPIView(APIView):
    """Create or reuse all database records required for a bound QR pass."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        name = str(request.data.get("name") or "").strip()
        event_id = request.data.get("event_id")
        session_id = request.data.get("session_id") or None

        if not name:
            return Response(
                {"detail": "Recipient name is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not event_id:
            return Response(
                {"detail": "Event is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            phone = normalize_whatsapp_phone(request.data.get("phone"))
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        event = Event.objects.filter(id=event_id).first()
        if not event:
            return Response({"detail": "Event not found."}, status=status.HTTP_404_NOT_FOUND)

        if not PermissionChecker.get_user_accessible_events(request.user).filter(id=event.id).exists():
            return Response(
                {"detail": "You do not have access to this event."},
                status=status.HTTP_403_FORBIDDEN,
            )

        session = None
        if session_id:
            session = Session.objects.filter(id=session_id, event=event).first()
            if not session:
                return Response(
                    {"detail": "The selected function does not belong to this event."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        with transaction.atomic():
            guest = find_guest_by_phone(phone, event)
            guest_created = guest is None
            if guest_created:
                guest = Guest.objects.create(name=name, phone=phone)

            event_registration, event_registration_created = EventRegistration.objects.get_or_create(
                guest=guest,
                event=event,
                defaults={"rsvp_status": "not_sent", "name_on_message": name},
            )

            session_registration = None
            session_registration_created = False
            if session:
                session_registration, session_registration_created = SessionRegistration.objects.get_or_create(
                    guest=guest,
                    session=session,
                )

        created_any_record = (
            guest_created
            or event_registration_created
            or session_registration_created
        )
        return Response(
            {
                "guest": {
                    "id": str(guest.id),
                    "name": guest.name,
                    "phone": guest.phone,
                },
                "event": {"id": str(event.id), "name": event.name},
                "event_registration": {"id": str(event_registration.id)},
                "session": (
                    {"id": str(session.id), "title": session.title}
                    if session
                    else None
                ),
                "session_registration": (
                    {"id": str(session_registration.id)}
                    if session_registration
                    else None
                ),
                "created": {
                    "guest": guest_created,
                    "event_registration": event_registration_created,
                    "session_registration": session_registration_created,
                },
            },
            status=status.HTTP_201_CREATED if created_any_record else status.HTTP_200_OK,
        )
