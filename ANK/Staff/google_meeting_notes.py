import re
from datetime import timedelta
from html.parser import HTMLParser
from urllib.parse import urlencode, urlsplit

from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from Staff.google_calendar_service import CalendarError, calendar_request, google_request


NOTES_SCOPES = (
    "https://www.googleapis.com/auth/meetings.space.readonly",
    "https://www.googleapis.com/auth/documents.readonly",
)
MEET_API = "https://meet.googleapis.com/v2"
DOCS_API = "https://docs.googleapis.com/v1"


def can_preview_notes(user):
    return (
        settings.GOOGLE_MEETING_NOTES_PILOT
        and (user.is_superuser or user.role in {"admin", "super_admin"})
        and user.email.casefold() == settings.GOOGLE_CALENDAR_ACCOUNT_EMAIL.casefold()
    )


def meeting_code(event):
    conference = event.get("conferenceData", {})
    if conference.get("conferenceSolution", {}).get("key", {}).get("type") == "hangoutsMeet":
        code = conference.get("conferenceId", "")
        if re.fullmatch(r"[a-z]{3}-[a-z]{4}-[a-z]{3}", code):
            return code
    for value in (event.get("hangoutLink", ""), event.get("location", "")):
        url = urlsplit(value.strip())
        if url.scheme == "https" and url.netloc == "meet.google.com":
            code = url.path.strip("/")
            if re.fullmatch(r"[a-z]{3}-[a-z]{4}-[a-z]{3}", code):
                return code
    return ""


def event_times(event):
    start = parse_datetime(event.get("start", {}).get("dateTime", ""))
    end = parse_datetime(event.get("end", {}).get("dateTime", ""))
    return (start, end) if start and end and start.tzinfo and end.tzinfo else (None, None)


class NotesLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.href = None
        self.label = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.href = dict(attrs).get("href")
            self.label = []

    def handle_data(self, data):
        if self.href:
            self.label.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.href:
            self.links.append(("".join(self.label), self.href))
            self.href = None


def attached_notes_documents(event):
    links = NotesLinks()
    links.feed(event.get("description") or "")
    candidates = links.links + [
        (attachment.get("title", ""), attachment.get("fileUrl", ""))
        for attachment in event.get("attachments", [])
    ]
    documents = {}
    for title, url in candidates:
        if not re.search(r"\b(gemini|notes?)\b", title or "", re.IGNORECASE):
            continue
        match = re.fullmatch(
            r"https://docs\.google\.com/document/d/([A-Za-z0-9_-]+)(?:[/?#].*)?",
            url or "",
        )
        if match:
            documents[match[1]] = title.strip()
    return documents


def can_lookup_event(event):
    start, end = event_times(event)
    return bool(
        start and end and end <= timezone.now()
        and event.get("status") != "cancelled"
        and event.get("visibility") not in {"private", "confidential"}
        and (meeting_code(event) or attached_notes_documents(event))
    )


def text_runs(value):
    if isinstance(value, list):
        for child in value:
            yield from text_runs(child)
    elif isinstance(value, dict):
        if "textRun" in value:
            yield value["textRun"]
        elif "richLink" in value:
            link = value["richLink"].get("richLinkProperties", {})
            yield {"content": link.get("title") or "", "textStyle": {"link": {"url": link.get("uri")}}}
        else:
            for child in value.values():
                yield from text_runs(child)


def notes_url(document_id):
    return f"https://docs.google.com/document/d/{document_id}/edit"


def select_notes_document(token, documents, document_id):
    if document_id is not None:
        if document_id not in documents:
            raise CalendarError("This notes document is not linked to the event.", 404)
        return read_notes_document(token, document_id)
    if len(documents) == 1:
        return read_notes_document(token, next(iter(documents)))
    return {"documents": [
        {"id": key, "title": title, "url": notes_url(key)}
        for key, title in documents.items()
    ]}


def preview_meeting_notes(token, event_id, *, calendar_token, document_id=None):
    event = calendar_request("GET", calendar_token, event_id)
    if not can_lookup_event(event):
        raise CalendarError("Choose a past Team Calendar event with Gemini notes or a Google Meet link.", 404)

    attached = attached_notes_documents(event)
    if attached:
        return select_notes_document(token, attached, document_id)

    start, end = event_times(event)
    if end < timezone.now() - timedelta(days=30):
        raise CalendarError("This meeting is outside Google's 30-day conference lookup window.", 404)

    earliest = (start - timedelta(minutes=30)).isoformat()
    latest = min(start + timedelta(minutes=30), end).isoformat()
    records = google_request("GET", f"{MEET_API}/conferenceRecords", token=token, params={
        "filter": f'space.meeting_code = "{meeting_code(event)}" '
                  f'AND start_time >= "{earliest}" AND start_time <= "{latest}"',
        "pageSize": 100,
    })
    candidates = []
    for record in records.get("conferenceRecords", []):
        actual_end = parse_datetime(record.get("endTime") or "")
        name = record.get("name", "")
        if actual_end and actual_end.tzinfo and actual_end > start and re.fullmatch(
            r"conferenceRecords/[A-Za-z0-9_-]+", name
        ):
            candidates.append(name)
    if records.get("nextPageToken") or len(candidates) > 1:
        raise CalendarError("More than one Google Meet call could match this event.", 409)
    if not candidates:
        raise CalendarError("Google Meet returned no completed call matching this event.", 404)

    documents = {}
    params = {"pageSize": 100}
    while True:
        response = google_request(
            "GET", f"{MEET_API}/{candidates[0]}/smartNotes", token=token, params=params,
        )
        for note in response.get("smartNotes", []):
            document = note.get("docsDestination", {}).get("document", "")
            if note.get("state") == "FILE_GENERATED" and re.fullmatch(r"[A-Za-z0-9_-]+", document):
                documents.setdefault(document, f"Gemini notes document {len(documents) + 1}")
        if not response.get("nextPageToken"):
            break
        params = {**params, "pageToken": response["nextPageToken"]}

    if not documents:
        raise CalendarError("Google Meet has no generated Gemini notes for this call.", 404)
    return select_notes_document(token, documents, document_id)


def notes_links(runs, document_url):
    labels = {}
    for run in runs:
        link = run.get("textStyle", {}).get("link", {})
        url = link.get("url") or ""
        if not url and link.get("tabId"):
            url = f"{document_url}?{urlencode({'tab': link['tabId']})}"
        elif not url and link.get("heading"):
            heading = link["heading"]
            url = f"{document_url}?{urlencode({'tab': heading.get('tabId', '')})}"
            url += f"#{urlencode({'heading': heading.get('id', '')})}"
        elif not url and link.get("bookmark"):
            bookmark = link["bookmark"]
            url = f"{document_url}?{urlencode({'tab': bookmark.get('tabId', '')})}"
            url += f"#{urlencode({'bookmark': bookmark.get('id', '')})}"
        if url.startswith(("https://docs.google.com/", "https://drive.google.com/")):
            labels[url] = labels.get(url, "") + run.get("content", "")
    return [
        {"title": label.strip(), "url": url}
        for url, label in labels.items()
        if re.search(r"\b(?:notes?|next steps|action items|details)\b", label, re.IGNORECASE)
    ]


def read_notes_document(token, document_id):
    document = google_request(
        "GET", f"{DOCS_API}/documents/{document_id}", token=token,
        params={"includeTabsContent": "true"},
    )
    body = document.get("body", {})
    tabs = document.get("tabs", [])
    if tabs:
        notes_tab = next(
            (tab for tab in tabs if "notes" in tab.get("tabProperties", {}).get("title", "").lower()),
            tabs[0],
        )
        title = notes_tab.get("tabProperties", {}).get("title", "").lower()
        body = {} if "transcript" in title else notes_tab.get("documentTab", {}).get("body", {})
    runs = list(text_runs(body.get("content", [])))
    text = "".join(run.get("content", "") for run in runs).strip()
    url = notes_url(document_id)
    return {
        "title": document.get("title", "Gemini notes"),
        "text": text[:24000],
        "truncated": len(text) > 24000,
        "url": url,
        "links": notes_links(runs, url),
    }
