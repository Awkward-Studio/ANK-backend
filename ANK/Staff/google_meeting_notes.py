import re
from datetime import timedelta
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlencode, urlsplit

from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from Staff.google_calendar_service import CalendarError, calendar_request, google_request
from Staff.google_docs_content import decision_groups, discussion_topics, meeting_summary, render_content, suggested_steps


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


def select_notes_document(token, documents, document_id, *, steps_only=False, overview_only=False):
    if steps_only:
        steps = []
        decisions = []
        for key in documents:
            document = read_notes_document(token, key, steps_only=True)
            steps.extend(document["suggested_steps"])
            decisions.extend(document["decisions"])
        return {"suggested_steps": steps, "decisions": decisions}
    if document_id is not None:
        if document_id not in documents:
            raise CalendarError("This notes document is not linked to the event.", 404)
        return read_notes_document(token, document_id, overview_only=overview_only)
    if len(documents) == 1:
        return read_notes_document(token, next(iter(documents)), overview_only=overview_only)
    return {"documents": [
        {"id": key, "title": title, "url": notes_url(key)}
        for key, title in documents.items()
    ]}


def preview_meeting_notes(token, event_id, *, calendar_token, document_id=None, steps_only=False):
    event = calendar_request("GET", calendar_token, event_id)
    return read_event_notes(token, event, document_id=document_id, steps_only=steps_only)


def read_event_notes(token, event, *, document_id=None, steps_only=False, overview_only=False):
    if not can_lookup_event(event):
        raise CalendarError("Choose a past Team Calendar event with Gemini notes or a Google Meet link.", 404)

    attached = attached_notes_documents(event)
    if attached:
        return {
            **select_notes_document(token, attached, document_id, steps_only=steps_only, overview_only=overview_only),
            "meeting_title": event.get("summary", ""),
        }

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
    return {
        **select_notes_document(token, documents, document_id, steps_only=steps_only, overview_only=overview_only),
        "meeting_title": event.get("summary", ""),
    }


def document_link(link, document_url):
    if link.get("url"):
        return link["url"]
    if link.get("tabId"):
        return f"{document_url}?{urlencode({'tab': link['tabId']})}"
    for kind in ("heading", "bookmark"):
        if target := link.get(kind):
            query = f"?{urlencode({'tab': target['tabId']})}" if target.get("tabId") else ""
            return f"{document_url}{query}#{urlencode({kind: target.get('id', '')})}"
    return ""


def notes_links(runs, document_url):
    labels = {}
    for run in runs:
        url = document_link(run.get("textStyle", {}).get("link", {}), document_url)
        if url.startswith(("https://docs.google.com/", "https://drive.google.com/")):
            labels[url] = labels.get(url, "") + run.get("content", "")
    return [
        {"title": label.strip(), "url": url}
        for url, label in labels.items()
        if re.search(r"\b(?:notes?|next steps|action items|details|transcript)\b", label, re.IGNORECASE)
    ]


def document_tabs(tabs):
    for tab in tabs:
        yield tab
        yield from document_tabs(tab.get("childTabs", []))


def tab_title(tab):
    return tab.get("tabProperties", {}).get("title", "").casefold()


def tab_runs(tab):
    body = tab.get("documentTab", {}).get("body", {})
    return list(text_runs(body.get("content", [])))


def full_notes_label(title):
    return re.search(r"\bfull (?:meeting )?notes\b", title, re.IGNORECASE)


def fetch_document(token, document_id):
    return google_request(
        "GET", f"{DOCS_API}/documents/{document_id}", token=token,
        params={"includeTabsContent": "true"},
    )



def render_tab(data, document_url):
    return render_content(
        data.get("body", {}).get("content", []),
        lambda link: document_link(link, document_url), data.get("lists", {}),
    )


def linked_document_tab(token, link, kind, current_id, *, steps_only=False, overview_only=False):
    target = urlsplit(link["url"])
    match = re.fullmatch(r"/document/(?:u/\d+/)?d/([A-Za-z0-9_-]+)(?:/[^/]*)?/?", target.path)
    if target.netloc != "docs.google.com" or not match or match[1] == current_id:
        return None
    try:
        document = fetch_document(token, match[1])
    except CalendarError:
        if steps_only:
            raise
        return None
    tabs = list(document_tabs(document.get("tabs", [])))
    requested = parse_qs(target.query).get("tab", [None])[0]
    if requested:
        tab = next((item for item in tabs if item.get("tabProperties", {}).get("tabId") == requested), None)
    elif kind == "transcript":
        tab = next((item for item in tabs if "transcript" in tab_title(item)), tabs[0] if tabs else None)
    else:
        tab = next((item for item in tabs if full_notes_label(tab_title(item))), tabs[0] if tabs else None)
    data = tab.get("documentTab", {}) if tab else document
    return {
        "id": f"linked-{kind}",
        "title": link["title"],
        "kind": kind,
        "url": link["url"],
        "html": "" if steps_only or overview_only else render_tab(data, notes_url(match[1])),
    }, list(text_runs(data.get("body", {}).get("content", [])))


def read_notes_document(token, document_id, *, steps_only=False, overview_only=False):
    document = fetch_document(token, document_id)
    url = notes_url(document_id)
    original_url = url
    all_tabs = list(document_tabs(document.get("tabs", [])))
    tabs = [tab for tab in all_tabs if "transcript" not in tab_title(tab)]
    full_tab = None
    notes_tab = None
    links = []
    if tabs:
        notes_tab = next((tab for tab in tabs if "notes" in tab_title(tab)), tabs[0])
        runs = tab_runs(notes_tab)
        links = notes_links(runs, url)
        tabs_by_id = {
            tab["tabProperties"]["tabId"]: tab
            for tab in tabs if tab.get("tabProperties", {}).get("tabId")
        }
        full_tab = next((tab for tab in tabs if full_notes_label(tab_title(tab))), None)
        full_url = None
        for link in links:
            if not full_notes_label(link["title"]):
                continue
            target = urlsplit(link["url"])
            if target._replace(query="", fragment="").geturl() != url:
                continue
            tab_id = parse_qs(target.query).get("tab", [None])[0]
            if tab_id in tabs_by_id:
                full_tab = tabs_by_id[tab_id]
                full_url = link["url"]
                break
        if full_tab is not None:
            full_runs = tab_runs(full_tab)
            if full_runs:
                runs = full_runs
                tab_id = full_tab.get("tabProperties", {}).get("tabId")
                original_url = full_url or (f"{url}?{urlencode({'tab': tab_id})}" if tab_id else url)
    elif document.get("tabs"):
        runs = []
    else:
        runs = list(text_runs(document.get("body", {}).get("content", [])))

    links_by_url = {link["url"]: link for link in links + notes_links(runs, url)}
    text = "".join(run.get("content", "") for run in runs).strip()
    sections = []
    quick_summaries = []
    if not all_tabs:
        all_tabs = [{"tabProperties": {"title": "Full notes"}, "documentTab": document}]
    for index, tab in enumerate([] if steps_only else all_tabs):
        props = tab.get("tabProperties", {})
        tab_id = props.get("tabId")
        title = props.get("title") or f"Document tab {index + 1}"
        if "transcript" in title.casefold():
            kind = "transcript"
        elif tab is full_tab or not document.get("tabs"):
            kind = "full"
        elif re.search(r"quick|summary", title, re.IGNORECASE):
            kind = "quick"
        elif tab is notes_tab and full_tab is None:
            kind = "full"
        elif tab is notes_tab:
            kind = "quick"
        else:
            kind = "other"
        data = tab.get("documentTab", {})
        if kind == "quick":
            quick_text = "".join(run.get("content", "") for run in tab_runs(tab))
            quick_summary = meeting_summary(quick_text, quick=True)
            if quick_summary:
                quick_summaries.append(quick_summary)
        sections.append({
            "id": tab_id or f"tab-{index}",
            "title": title,
            "kind": kind,
            "url": f"{url}?{urlencode({'tab': tab_id})}" if tab_id else url,
            "html": "" if overview_only else render_tab(data, url),
        })
    for kind in (("full",) if steps_only or overview_only else ("full", "transcript")):
        if (kind == "full" and full_tab is not None) or (
            kind == "transcript" and any(section["kind"] == kind for section in sections)
        ):
            continue
        matches = (link for link in links_by_url.values() if (
            full_notes_label(link["title"]) if kind == "full" else link["title"].casefold() == "transcript"
        ))
        link = next(matches, None)
        if link:
            linked = linked_document_tab(
                token, link, kind, document_id, steps_only=steps_only, overview_only=overview_only,
            )
            if not linked:
                continue
            section, linked_runs = linked
            if kind == "full":
                for existing in sections:
                    if existing["kind"] == "full":
                        existing["kind"] = "quick"
                if not steps_only:
                    quick_summary = meeting_summary(text, quick=True)
                    if quick_summary:
                        quick_summaries.append(quick_summary)
                original_url = section["url"]
                text = "".join(run.get("content", "") for run in linked_runs).strip()
            sections.append(section)
    decisions = decision_groups(text)
    if steps_only:
        return {"suggested_steps": suggested_steps(text), "decisions": decisions}
    full_summary = meeting_summary(text)
    return {
        "document_id": document_id,
        "tabs": sections,
        "decisions": decisions,
        "summary_text": full_summary,
        "overview": {
            "quick_summaries": list(dict.fromkeys(quick_summaries)),
            "full_summary": full_summary,
            "discussion_topics": discussion_topics(text),
        },
        "suggested_steps": suggested_steps(text),
        "title": document.get("title", "Gemini notes"),
        "text": "" if overview_only else text[:24000],
        "truncated": not overview_only and len(text) > 24000,
        "url": original_url,
        "links": list(links_by_url.values()),
    }
