import re
from urllib.parse import urlsplit

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404

from Departments.permissions import PermissionChecker
from Staff.google_calendar_service import CalendarError
from Staff.models import MeetingEventLink


UUID = r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}"


def event_option(event):
    return {"id": str(event.pk), "name": event.name, "start_date": event.start_date}


def available_meeting(event):
    return event.get("status") != "cancelled" and event.get("visibility") not in {"private", "confidential"}


def find_explicit_event(meeting):
    origin = urlsplit(settings.GOOGLE_CALENDAR_APP_ORIGIN)
    links = re.findall(r"https?://[^\s<>\"']+", " ".join(
        (meeting.get("description") or "", meeting.get("location") or "")
    ))
    identities = set()
    for url in links:
        try:
            target = urlsplit(url)
        except ValueError:
            continue
        if (target.scheme, target.netloc) != (origin.scheme, origin.netloc):
            continue
        match = re.fullmatch(rf"/events/({UUID})(?:/[^\s]*)?", target.path, re.IGNORECASE)
        if match:
            identities.add(match[1].lower())
    return next(iter(identities)) if len(identities) == 1 else None


def normalized(text):
    return " ".join(re.findall(r"[^\W_]+", (text or "").casefold()))


def candidates(meeting, events, term):
    if term:
        return [
            event_option(event)
            for event in events.filter(Q(name__icontains=term) | Q(client_name__icontains=term)).order_by("name", "id")[:12]
        ]
    title = f" {normalized(meeting.get('summary'))} "
    scored = []
    for event in events.only("id", "name", "client_name", "start_date").iterator():
        name = normalized(event.name)
        client = normalized(event.client_name)
        if not name or len(name) < 5 or f" {name} " not in title:
            continue
        scored.append((int(title.strip() == name), len(name), int(bool(client and f" {client} " in title)), event))
    scored.sort(key=lambda item: (-item[0], -item[1], -item[2], item[3].name.casefold(), str(item[3].pk)))
    return [event_option(item[3]) for item in scored[:5]]


def meeting_link(event_id):
    return MeetingEventLink.objects.filter(
        calendar_id=settings.GOOGLE_CALENDAR_ID, meeting_id=event_id,
    ).select_related("event").first()


def visible_event(user, event):
    if event and PermissionChecker.get_user_accessible_events(user).filter(pk=event.pk).exists():
        return event_option(event)
    return None


def change_link(user, meeting, event_id, *, automatic=False):
    if not available_meeting(meeting):
        raise CalendarError("This meeting is private or no longer available.", 404)
    events = PermissionChecker.get_user_accessible_events(user)
    event = get_object_or_404(events, pk=event_id) if event_id else None
    with transaction.atomic():
        link, _ = MeetingEventLink.objects.select_for_update().get_or_create(
            calendar_id=settings.GOOGLE_CALENDAR_ID, meeting_id=meeting["id"],
        )
        if not automatic or not (link.event_id or link.automatic_disabled):
            link.event = event
            link.automatic_disabled = event is None
            link.save(update_fields=["event", "automatic_disabled"])
    return visible_event(user, link.event)
