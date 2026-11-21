import hashlib
import json

from django.conf import settings
from rest_framework.exceptions import PermissionDenied

from Staff.google_calendar_service import CalendarError, access_token, calendar_request, connection
from Staff.google_docs_content import is_discussion_group
from Staff.google_meeting_notes import (
    attached_notes_documents,
    can_lookup_event,
    can_preview_notes,
    meeting_code,
    read_event_notes,
    read_notes_document,
)
from Staff.models import MeetingNotesOverview, TeamTask
from Staff.team_tasks import source_key, step_key


def source_revision(event):
    source = [
        event.get("start", {}).get("dateTime"),
        event.get("end", {}).get("dateTime"),
        meeting_code(event),
        list(attached_notes_documents(event).items()),
    ]
    return hashlib.sha256(json.dumps(source).encode()).hexdigest()


def on_meeting_invite(user, event):
    if not settings.GOOGLE_MEETING_NOTES_PILOT or not user.google_login_subject:
        return False
    email = user.email.casefold()
    organizer = event.get("organizer", {})
    return organizer.get("email", "").casefold() == email or any(
        guest.get("email", "").casefold() == email and not guest.get("resource")
        for guest in event.get("attendees", [])
    )


def build_picker_data(calendar_id, event_id, payload):
    if "documents" in payload:
        return {"document_ids": [document["id"] for document in payload["documents"]]}

    decisions, discussion = set(), set()
    for group in payload["decisions"]:
        bucket = discussion if is_discussion_group(group["label"]) else decisions
        bucket.update(item.casefold() for item in group["items"])
    return {
        "document_id": payload["document_id"],
        "keys": sorted({
            source_key(calendar_id, event_id, step_key(step)) for step in payload["suggested_steps"]
        }),
        "decisions": sorted(decisions),
        "discussion": sorted(discussion),
    }


def meeting_notes(user, event_id, document_id, *, overview, refresh=False, importing=False):
    owner = can_preview_notes(user)
    if not owner and (
        not settings.GOOGLE_MEETING_NOTES_PILOT or not overview
        or refresh or importing or not user.google_login_subject
    ):
        raise PermissionDenied()
    saved_connection = connection()
    if not saved_connection or not saved_connection.notes_refresh_token:
        raise CalendarError("Connect Gemini notes from Team Calendar first.", 409)
    event = calendar_request("GET", access_token(), event_id)
    if not can_lookup_event(event):
        raise CalendarError("Choose a past Team Calendar event with Gemini notes or a Google Meet link.", 404)

    if not owner and not on_meeting_invite(user, event):
        raise PermissionDenied()

    revision = source_revision(event)
    keys = {
        "calendar_id": settings.GOOGLE_CALENDAR_ID,
        "account_email": saved_connection.account_email.casefold(),
        "event_id": event_id,
    }
    snapshots = MeetingNotesOverview.objects.filter(**keys, source_revision=revision)
    selector = document_id or ""
    snapshot = snapshots.filter(document_selector=selector).first()
    if snapshot is None and document_id:
        default = snapshots.filter(document_selector="").first()
        if default and default.payload.get("document_id") == document_id:
            snapshot = default
    if overview and not refresh and not importing and snapshot:
        if not owner and "documents" in snapshot.payload:
            cached_ids = {
                data.get("document_id") for data in snapshots.values_list("picker_data", flat=True)
            }
            documents = [item for item in snapshot.payload["documents"] if item["id"] in cached_ids]
            if not documents:
                raise CalendarError("This meeting overview hasn’t been imported yet.", 404)
            return {**snapshot.payload, "documents": documents}
        return snapshot.payload
    if not owner:
        raise CalendarError("This meeting overview hasn’t been imported yet.", 404)

    try:
        token = access_token(notes=True)
        known_document = snapshot.payload.get("document_id") if snapshot else None
        if known_document:
            # The current event still matches the source that originally resolved this document.
            # Google Docs checks access even when the Meet lookup window has expired.
            data = read_notes_document(token, known_document, overview_only=overview)
            data["meeting_title"] = event.get("summary", "")
        else:
            data = read_event_notes(token, event, document_id=document_id, overview_only=overview)
    except CalendarError as error:
        if snapshot and error.status_code in {403, 404, 410, 424}:
            document_key = snapshot.payload.get("document_id")
            if document_key:
                snapshots.filter(payload__document_id=document_key).delete()
            else:
                snapshot.delete()
        raise
    if overview and not importing:
        data.pop("tabs", None)
        data.pop("links", None)
        MeetingNotesOverview.objects.update_or_create(
            **keys, document_selector=snapshot.document_selector if snapshot else selector,
            defaults={
                "source_revision": revision,
                "payload": data,
                "picker_data": build_picker_data(keys["calendar_id"], event_id, data),
            },
        )
    return data


def picker_overviews(user, events):
    owner = can_preview_notes(user)
    if not owner and (not settings.GOOGLE_MEETING_NOTES_PILOT or not user.google_login_subject):
        return {}
    saved_connection = connection()
    if not saved_connection or not saved_connection.notes_refresh_token:
        return {}

    revisions = {
        event["id"]: source_revision(event) for event in events
        if can_lookup_event(event) and (owner or on_meeting_invite(user, event))
    }
    rows = MeetingNotesOverview.objects.filter(
        calendar_id=settings.GOOGLE_CALENDAR_ID,
        account_email=saved_connection.account_email.casefold(),
        event_id__in=revisions,
    ).values_list("event_id", "source_revision", "picker_data")
    documents = {}
    expected = {}
    for event_id, revision, data in rows:
        if revision != revisions[event_id]:
            continue
        if "document_ids" in data:
            expected[event_id] = set(data["document_ids"])
        else:
            documents.setdefault(event_id, {})[data["document_id"]] = data

    summaries, task_keys = {}, {}
    for event_id, meeting_documents in documents.items():
        known_ids = expected.get(event_id, meeting_documents.keys())
        visible_documents = [data for key, data in meeting_documents.items() if key in known_ids]
        if not visible_documents:
            continue
        keys = {key for data in visible_documents for key in data["keys"]}
        decisions = {decision for data in visible_documents for decision in data["decisions"]}
        discussion = {point for data in visible_documents for point in data["discussion"]}
        task_keys[event_id] = keys
        summaries[event_id] = {
            "total": len(keys),
            "decisions": len(decisions),
            "discussion": len(discussion),
            "partial": len(visible_documents) < len(known_ids),
        }
    saved = set(TeamTask.objects.filter(
        source_key__in=set().union(*task_keys.values()), meeting_link__isnull=False,
    ).values_list("source_key", flat=True))
    for event_id, keys in task_keys.items():
        summaries[event_id]["saved"] = len(keys & saved)
    return summaries
