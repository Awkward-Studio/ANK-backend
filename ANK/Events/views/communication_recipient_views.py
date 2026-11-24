import re

from django.core.exceptions import ValidationError as DjangoValidationError
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


class RecipientRegistrationError(Exception):
    def __init__(self, detail, status_code=status.HTTP_400_BAD_REQUEST):
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


def resolve_recipient_scope(user, event_id, session_id=None):
    if not event_id:
        raise RecipientRegistrationError("Event is required.")

    try:
        event = Event.objects.filter(id=event_id).first()
    except (DjangoValidationError, ValueError, TypeError):
        event = None
    if not event:
        raise RecipientRegistrationError("Event not found.", status.HTTP_404_NOT_FOUND)

    if not PermissionChecker.get_user_accessible_events(user).filter(id=event.id).exists():
        raise RecipientRegistrationError(
            "You do not have access to this event.",
            status.HTTP_403_FORBIDDEN,
        )

    session = None
    if session_id:
        try:
            session = Session.objects.filter(id=session_id, event=event).first()
        except (DjangoValidationError, ValueError, TypeError):
            session = None
        if not session:
            raise RecipientRegistrationError(
                "The selected function does not belong to this event."
            )
    return event, session


def register_communication_recipient(name, phone, event, session=None):
    normalized_phone = normalize_whatsapp_phone(phone)
    guest = find_guest_by_phone(normalized_phone, event)
    guest_created = guest is None
    if guest_created:
        guest = Guest.objects.create(name=name, phone=normalized_phone)

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

    created = {
        "guest": guest_created,
        "event_registration": event_registration_created,
        "session_registration": session_registration_created,
    }
    binding = {
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
        "created": created,
    }
    return binding, any(created.values())


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
        try:
            phone = normalize_whatsapp_phone(request.data.get("phone"))
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        try:
            event, session = resolve_recipient_scope(request.user, event_id, session_id)
        except RecipientRegistrationError as exc:
            return Response({"detail": exc.detail}, status=exc.status_code)

        with transaction.atomic():
            # Serialize recipient creation per event so concurrent uploads cannot
            # create two guest rows for the same new phone before either commits.
            event = Event.objects.select_for_update().get(pk=event.pk)
            binding, created_any_record = register_communication_recipient(
                name, phone, event, session
            )
        return Response(
            binding,
            status=status.HTTP_201_CREATED if created_any_record else status.HTTP_200_OK,
        )


class BulkCommunicationRecipientRegistrationAPIView(APIView):
    """Register a deduplicated CSV audience against one event/function scope."""

    permission_classes = [IsAuthenticated]
    max_recipients = 1000

    def post(self, request):
        recipients = request.data.get("recipients")
        if not isinstance(recipients, list) or not recipients:
            return Response(
                {"detail": "At least one CSV recipient is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(recipients) > self.max_recipients:
            return Response(
                {"detail": f"A maximum of {self.max_recipients} recipients can be registered at once."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            event, session = resolve_recipient_scope(
                request.user,
                request.data.get("event_id"),
                request.data.get("session_id") or None,
            )
        except RecipientRegistrationError as exc:
            return Response({"detail": exc.detail}, status=exc.status_code)

        prepared = []
        errors = []
        duplicate_rows = []
        seen_phones = set()
        for index, recipient in enumerate(recipients):
            csv_row = index + 2
            if not isinstance(recipient, dict):
                errors.append({"row": csv_row, "detail": "Recipient must be an object."})
                continue
            name = str(recipient.get("name") or "").strip()
            if not name:
                errors.append({"row": csv_row, "detail": "Recipient name is required."})
                continue
            try:
                phone = normalize_whatsapp_phone(recipient.get("phone"))
            except ValueError as exc:
                errors.append({"row": csv_row, "detail": str(exc)})
                continue
            if phone in seen_phones:
                duplicate_rows.append(csv_row)
                continue
            seen_phones.add(phone)
            prepared.append({"source_index": index, "name": name, "phone": phone})

        if errors:
            return Response(
                {"detail": "Fix the invalid CSV rows and upload the file again.", "errors": errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        bindings = []
        created_any_record = False
        with transaction.atomic():
            event = Event.objects.select_for_update().get(pk=event.pk)
            for recipient in prepared:
                binding, created = register_communication_recipient(
                    recipient["name"],
                    recipient["phone"],
                    event,
                    session,
                )
                bindings.append({"source_index": recipient["source_index"], **binding})
                created_any_record = created_any_record or created

        return Response(
            {
                "recipients": bindings,
                "duplicates_skipped": len(duplicate_rows),
                "duplicate_rows": duplicate_rows,
            },
            status=status.HTTP_201_CREATED if created_any_record else status.HTTP_200_OK,
        )
