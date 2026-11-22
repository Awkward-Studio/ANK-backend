import re
from urllib.parse import urlsplit

from django.utils.dateparse import parse_date

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
    title = normalized(meeting.get("summary"))
    ignored = {"a", "an", "and", "for", "the", "with", "event", "festival", "meeting", "call", "review", "planning", "wedding", "sync"}
    title_words = set(title.split()) - ignored
    start = meeting.get("start", {})
    day = parse_date((start.get("dateTime") or start.get("date") or "")[:10])
    ranked = []
    for event in events.only("id", "name", "client_name", "start_date").iterator():
        name = normalized(event.name)
        client = normalized(event.client_name)
        words = set(name.split()) - ignored
        shared = words & title_words
        exact = bool(name and name == title)
        full_name = bool(words and f" {name} " in f" {title} ")
        client_match = bool(set(client.split()) - ignored and f" {client} " in f" {title} ")
        partial = bool(shared and (len(shared) >= 2 or any(len(word) >= 5 for word in shared)))
        tier = 4 if exact else 3 if full_name else 2 if partial else 1 if client_match else 0
        distance = abs((event.start_date - day).days) if day and event.start_date else float("inf")
        ranked.append((-tier, -len(shared), distance, event.name.casefold(), str(event.pk), event))
    ranked.sort(key=lambda item: item[:5])
    matches = [item for item in ranked if item[0] < 0]
    return [
        {**event_option(item[-1]), "suggested": item[0] < 0}
        for item in (matches or ranked)[:5]
    ]


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
