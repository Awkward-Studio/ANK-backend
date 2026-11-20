from datetime import timedelta
from unittest.mock import patch
from urllib.parse import quote

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from Staff.google_calendar_service import CalendarError, EVENT_SCOPE, cipher
from Staff.google_meeting_notes import NOTES_SCOPES
from Staff.models import GoogleCalendarConnection, TeamTask, User


BASE = "/api/team-calendar/"
NOTES = BASE + "events/event-1/notes/"


@override_settings(
    GOOGLE_MEETING_NOTES_PILOT=True,
    GOOGLE_CALENDAR_CLIENT_ID="test-client.apps.googleusercontent.com",
    GOOGLE_CALENDAR_CLIENT_SECRET="fixture",
    GOOGLE_CALENDAR_ACCOUNT_EMAIL="owner@example.com",
    GOOGLE_CALENDAR_APP_ORIGIN="https://rsvp.anewknot.com",
    GOOGLE_CALENDAR_REDIRECT_URI="https://api.anewknot.com/api/auth/google/calendar/callback/",
    GOOGLE_CALENDAR_ID="staff@group.calendar.google.com",
)
class GoogleMeetingNotesTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create_user("owner@example.com", role="admin")
        self.client.force_authenticate(self.owner)
        self.connection = GoogleCalendarConnection.objects.create(
            calendar_id="staff@group.calendar.google.com",
            account_email=self.owner.email,
            client_id="test-client.apps.googleusercontent.com",
            refresh_token="ordinary-calendar-token",
        )
        self.start = timezone.now() - timedelta(hours=2)
        self.end = self.start + timedelta(hours=1)
        self.event = {
            "id": "event-1",
            "hangoutLink": "https://meet.google.com/abc-defg-hij",
            "start": {"dateTime": self.start.isoformat()},
            "end": {"dateTime": self.end.isoformat()},
        }

    @patch("Staff.google_calendar.access_token")
    def test_other_admin_cannot_read_owners_notes(self, token):
        other = User.objects.create_user("other@example.com", role="admin")
        self.client.force_authenticate(other)
        self.assertEqual(self.client.get(NOTES).status_code, 403)
        token.assert_not_called()

    @override_settings(GOOGLE_MEETING_NOTES_PILOT=False)
    @patch("Staff.google_calendar.access_token")
    def test_pilot_is_disabled_without_the_flag(self, token):
        self.assertEqual(self.client.get(NOTES).status_code, 403)
        token.assert_not_called()

    def test_notes_consent_requests_only_notes_scopes(self):
        response = self.client.post(BASE + "connect/", {"notes": True}, format="json")
        self.assertEqual(response.status_code, 200)
        for scope in NOTES_SCOPES:
            self.assertIn(quote(scope, safe=""), response.json()["authorization_url"])
        self.assertNotIn(quote(EVENT_SCOPE, safe=""), response.json()["authorization_url"])
        status = self.client.get(BASE + "connection/").json()
        self.assertTrue(status["can_schedule"])
        self.assertTrue(status["can_connect_notes"])
        self.assertFalse(status["notes_connected"])

    @patch("Staff.google_calendar.google_request")
    @patch("Staff.google_calendar.token_request")
    def test_consent_saves_notes_token_without_changing_calendar_token(self, exchange, identity):
        identity.return_value = {"email": self.owner.email, "email_verified": True}
        exchange.return_value = {
            "scope": " ".join(NOTES_SCOPES),
            "access_token": "notes-access",
            "refresh_token": "notes-refresh",
        }
        attempt = self.client.post(BASE + "connect/", {"notes": True}, format="json").json()
        self.assertEqual(self.client.get("/api/auth/google/calendar/callback/", {
            "state": attempt["state"], "code": "mock-code",
        }).status_code, 302)
        self.assertEqual(self.client.post(BASE + "connect/complete/", {
            "state": attempt["state"], "verifier": attempt["verifier"],
        }).status_code, 200)
        self.connection.refresh_from_db()
        self.assertEqual(self.connection.refresh_token, "ordinary-calendar-token")
        self.assertEqual(cipher().decrypt(self.connection.notes_refresh_token.encode()), b"notes-refresh")

    @patch("Staff.google_calendar.access_token", return_value="access")
    @patch("Staff.google_meeting_notes.calendar_request")
    @patch("Staff.google_meeting_notes.google_request")
    def test_reads_notes_tab_for_single_matching_call(self, google, calendar, _token):
        calendar.return_value = self.event
        google.side_effect = [
            {"conferenceRecords": [{
                "name": "conferenceRecords/first",
                "endTime": self.end.isoformat(),
            }]},
            {"smartNotes": [{
                "state": "FILE_GENERATED",
                "docsDestination": {"document": "test-document"},
            }]},
            {"title": "Past meeting", "tabs": [
                {"tabProperties": {"title": "Transcript"}},
                {"tabProperties": {"title": "Notes by Gemini"}, "documentTab": {"body": {
                    "content": [{"paragraph": {"elements": [
                        {"textRun": {"content": "Review the schedule.\n"}},
                    ]}}],
                }}},
            ]},
        ]
        response = self.client.get(NOTES)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["text"], "Review the schedule.")
        self.assertIn("no-store", response["Cache-Control"])
        calendar.assert_called_once_with("GET", "access", "event-1")
        self.assertIn("abc-defg-hij", google.call_args_list[0].kwargs["params"]["filter"])
        self.assertIn("conferenceRecords/first/smartNotes", google.call_args_list[1].args[1])

    @patch("Staff.google_calendar.access_token", return_value="access")
    @patch("Staff.google_meeting_notes.calendar_request")
    @patch("Staff.google_meeting_notes.google_request")
    def test_ambiguous_conference_is_rejected_before_reading_notes(self, google, calendar, _token):
        calendar.return_value = self.event
        google.return_value = {"conferenceRecords": [
            {"name": f"conferenceRecords/{name}", "endTime": self.end.isoformat()}
            for name in ("first", "second")
        ]}
        self.assertEqual(self.client.get(NOTES).status_code, 409)
        self.assertEqual(google.call_count, 1)


    @patch("Staff.google_calendar.access_token", return_value="access")
    @patch("Staff.google_meeting_notes.calendar_request")
    @patch("Staff.google_meeting_notes.google_request")
    def test_copied_event_reads_attached_notes_without_meet_link(self, google, calendar, _token):
        event = dict(self.event)
        del event["hangoutLink"]
        event["start"] = {"dateTime": (self.start - timedelta(days=60)).isoformat()}
        event["end"] = {"dateTime": (self.end - timedelta(days=60)).isoformat()}
        event["attachments"] = [
            {"title": "Recording", "fileUrl": "https://drive.google.com/file/d/recording/view"},
            {"title": "Client call - Notes by Gemini", "fileUrl": "https://docs.google.com/document/d/notes-id/edit"},
        ]
        calendar.return_value = event
        google.return_value = {"title": "Client notes"}
        response = self.client.get(NOTES)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["url"], "https://docs.google.com/document/d/notes-id/edit")
        google.assert_called_once_with(
            "GET", "https://docs.googleapis.com/v1/documents/notes-id",
            token="access", params={"includeTabsContent": "true"},
        )

    @patch("Staff.google_calendar.access_token", return_value="access")
    @patch("Staff.google_meeting_notes.calendar_request")
    @patch("Staff.google_meeting_notes.google_request")
    def test_lists_distinct_documents_and_previews_only_event_documents(self, google, calendar, _token):
        first_url = "https://docs.google.com/document/d/first/edit"
        second_url = "https://docs.google.com/document/d/second/edit"
        calendar.return_value = {
            **self.event,
            "description": f'<a href="{first_url}">Notes</a>',
            "attachments": [
                {"title": "Summary notes", "fileUrl": first_url},
                {"title": "Full notes", "fileUrl": second_url},
            ],
        }
        response = self.client.get(NOTES)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["documents"], [
            {"id": "first", "title": "Summary notes", "url": first_url},
            {"id": "second", "title": "Full notes", "url": second_url},
        ])
        self.assertEqual(self.client.get(NOTES, {"document": "unrelated"}).status_code, 404)
        google.assert_not_called()

        google.side_effect = [{"body": {"content": [{"paragraph": {"elements": [
            {"textRun": {"content": "Open full ", "textStyle": {"link": {"url": first_url}}}},
            {"textRun": {"content": "notes", "textStyle": {"link": {"url": first_url}}}},
            {"textRun": {"content": "\nSuggested next steps\nReview the schedule.\n"}},
        ]}}]}}, CalendarError("Document inaccessible", 424)]
        response = self.client.get(NOTES, {"document": "second"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["url"], second_url)
        self.assertEqual(response.json()["links"], [{"title": "Open full notes", "url": first_url}])
        self.assertIn("Suggested next steps\nReview the schedule.", response.json()["text"])

    @patch("Staff.google_calendar.access_token", return_value="access")
    @patch("Staff.google_meeting_notes.calendar_request")
    @patch("Staff.google_meeting_notes.google_request")
    def test_lists_generated_documents_across_meet_pages(self, google, calendar, _token):
        calendar.return_value = self.event
        first = {"state": "FILE_GENERATED", "docsDestination": {"document": "first"}}
        second = {"state": "FILE_GENERATED", "docsDestination": {"document": "second"}}
        google.side_effect = [
            {"conferenceRecords": [{
                "name": "conferenceRecords/call",
                "endTime": self.end.isoformat(),
            }]},
            {"smartNotes": [first], "nextPageToken": "next"},
            {"smartNotes": [first, second]},
        ]

        response = self.client.get(NOTES)

        self.assertEqual(response.status_code, 200)
        self.assertEqual([doc["id"] for doc in response.json()["documents"]], ["first", "second"])
        self.assertEqual(google.call_count, 3)
        self.assertEqual(google.call_args.kwargs["params"]["pageToken"], "next")

    @patch("Staff.google_meeting_notes.google_request")
    def test_preview_follows_full_notes_link_to_nested_tab(self, google):
        from Staff.google_meeting_notes import read_notes_document

        def tab(tab_id, title, runs, child_tabs=()):
            return {
                "tabProperties": {"tabId": tab_id, "title": title},
                "documentTab": {"body": {"content": [
                    {"paragraph": {"elements": [{"textRun": run} for run in runs]}},
                ]}},
                "childTabs": list(child_tabs),
            }

        details = tab("t.details", "Details", [{"content": "Suggested next steps\nReview the schedule."}])
        google.return_value = {"tabs": [
            tab("t.summary", "Notes by Gemini", [
                {"content": "Want to see more? "},
                {"content": "View the full notes", "textStyle": {"link": {"tabId": "t.details"}}},
            ], [details]),
            tab("t.transcript", "Transcript", [{"content": "Private transcript"}]),
        ]}

        preview = read_notes_document("access", "meeting")
        full_url = "https://docs.google.com/document/d/meeting/edit?tab=t.details"
        self.assertEqual(preview["text"], "Suggested next steps\nReview the schedule.")
        self.assertEqual(preview["url"], full_url)
        self.assertEqual(preview["links"], [{"title": "View the full notes", "url": full_url}])

    @patch("Staff.google_calendar.access_token", return_value="access")
    @patch("Staff.google_meeting_notes.calendar_request")
    @patch("Staff.google_meeting_notes.google_request")
    def test_full_notes_drafts_are_idempotent_and_assignable_without_an_ank_event(self, google, calendar, _token):
        calendar.return_value = {
            **self.event, "summary": "Partner meeting",
            "attachments": [{"title": "Gemini notes", "fileUrl": "https://docs.google.com/document/d/notes/edit"}],
        }

        def tab(tab_id, title, paragraphs):
            return {
                "tabProperties": {"tabId": tab_id, "title": title},
                "documentTab": {"body": {"content": [{"paragraph": {
                    "elements": [{"textRun": {"content": line + "\n", "textStyle": {"bold": True}}}],
                }} for line in paragraphs]}},
            }

        google.return_value = {"tabs": [
            tab("quick", "Quick notes", ["Summary", "<script>unsafe markup</script>"]),
            tab("full", "Full notes", [
                "Decisions",
                "Partnership tiers",
                "Next steps",
                "[Internal Staff] Send Partnership Details: Send project details for review.",
                "[External Contact] Check Celebrity Availability: Verify scheduling.",
                "[External Contact] Review Event Proposal: Provide feedback on commercials.",
                "Details",
                "Partnership Next Steps: Narrative discussion outside the list.",
            ]),
            tab("transcript", "Transcript", ["(00:01:18) Internal Staff: Have you seen the proposal?"]),
        ]}
        payload = self.client.get(NOTES).json()
        tabs = {tab["kind"]: tab["html"] for tab in payload["tabs"]}
        self.assertIn("&lt;script&gt;", tabs["quick"])
        self.assertIn("<strong>Next steps</strong>", tabs["full"])
        self.assertIn("(00:01:18)", tabs["transcript"])
        self.assertEqual([step["title"] for step in payload["suggested_steps"]], [
            "Send Partnership Details", "Check Celebrity Availability", "Review Event Proposal",
        ])
        step = payload["suggested_steps"][0]
        self.assertFalse(step["saved"])
        self.assertEqual(self.client.post(NOTES, {"steps": ["0" * 64]}, format="json").status_code, 400)
        for _ in range(2):
            self.assertEqual(self.client.post(NOTES, {"steps": [step["id"]]}, format="json").status_code, 200)
        self.assertEqual(TeamTask.objects.count(), 1)
        self.assertTrue(self.client.get(NOTES).json()["suggested_steps"][0]["saved"])
        task = TeamTask.objects.get()
        self.assertEqual(task.status, TeamTask.Status.DRAFT)
        self.assertIsNone(task.due_date)
        self.assertIsNone(task.assignee)
        self.assertEqual(task.meeting_title, "Partner meeting")
        self.assertTrue(task.notes_url.endswith("?tab=full"))

        assignee = User.objects.create_user("staff@example.com", role="staff")
        endpoint = f"/api/team-tasks/{task.pk}/"
        self.client.force_authenticate(assignee)
        self.assertEqual(self.client.get("/api/team-tasks/").json()["tasks"], [])
        self.assertEqual(self.client.patch(endpoint, {"status": "todo"}, format="json").status_code, 404)
        self.client.force_authenticate(self.owner)
        response = self.client.patch(endpoint, {"assignee": str(assignee.pk), "status": "todo"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.client.force_authenticate(assignee)
        self.assertEqual(self.client.get("/api/team-tasks/").json()["tasks"][0]["title"], step["title"])
        self.assertEqual(self.client.patch(endpoint, {"title": "Edited"}, format="json").status_code, 403)
        self.assertEqual(self.client.patch(endpoint, {"status": "done"}, format="json").status_code, 200)
        self.client.force_authenticate(self.owner)
        self.assertEqual(self.client.get(NOTES).json()["suggested_steps"][0]["task_status"], "done")

    @patch("Staff.google_meeting_notes.google_request")
    def test_reads_transcript_document_linked_from_meeting_records(self, google):
        from Staff.google_meeting_notes import read_notes_document

        target_url = "https://docs.google.com/document/d/recording-transcript/edit"
        google.side_effect = [
            {"body": {"content": [{"paragraph": {"elements": [
                {"textRun": {"content": "Meeting records "}},
                {"textRun": {"content": "Transcript", "textStyle": {"link": {"url": target_url}}}},
            ]}}]}},
            {"body": {"content": [{"paragraph": {"elements": [
                {"textRun": {"content": "00:01:18 Speaker: Project details."}},
            ]}}]}},
        ]
        payload = read_notes_document("access", "notes")
        transcript = next(tab for tab in payload["tabs"] if tab["kind"] == "transcript")
        self.assertEqual(transcript["url"], target_url)
        self.assertIn("00:01:18 Speaker: Project details.", transcript["html"])
        self.assertEqual(payload["suggested_steps"], [])

    @patch("Staff.google_calendar.access_token", return_value="access")
    @patch("Staff.google_calendar.calendar_request")
    def test_explicit_links_attach_and_move_the_meeting_tasks(self, google, _token):
        from Events.models import Event
        from Staff.models import MeetingEventLink

        target = Event.objects.create(name="Partner Festival")
        other = Event.objects.create(name="Other Festival")
        google.return_value = {
            **self.event,
            "summary": "Partner Festival X Sponsor",
            "description": f'<a href="https://rsvp.anewknot.com/events/{target.pk}">ANK event</a>',
        }
        endpoint = BASE + "events/event-1/attachment/"
        response = self.client.get(endpoint)
        self.assertTrue(response.data["automatic_match"])
        self.assertTrue(response.data["suggestions"][0]["suggested"])
        self.assertEqual(response.data["suggestions"][0]["id"], str(target.pk))
        self.assertEqual(self.client.post(endpoint, {"automatic": True}, format="json").data["event"]["id"], str(target.pk))
        link = MeetingEventLink.objects.get()
        task = TeamTask.objects.create(
            source_key="test", title="Follow up", status=TeamTask.Status.TODO, meeting_link=link,
        )
        target_url = BASE + f"ank-events/{target.pk}/meetings/"
        other_url = BASE + f"ank-events/{other.pk}/meetings/"
        self.assertEqual(self.client.get(target_url).data["meetings"][0]["id"], "event-1")
        self.assertEqual(self.client.get(target_url).data["tasks"][0]["id"], task.pk)
        self.assertEqual(self.client.post(endpoint, {"event_id": str(other.pk)}, format="json").status_code, 200)
        self.assertEqual(self.client.get(target_url).data["tasks"], [])
        self.assertEqual(self.client.get(other_url).data["tasks"][0]["id"], task.pk)
        self.assertEqual(self.client.get("/api/team-tasks/").data["tasks"][0]["ank_event"]["id"], str(other.pk))
        self.assertEqual(self.client.post(endpoint, {"event_id": None}, format="json").status_code, 200)
        self.assertFalse(self.client.get(endpoint).data["automatic_match"])
        self.assertIsNone(self.client.get("/api/team-tasks/").data["tasks"][0]["ank_event"])
        self.assertEqual(TeamTask.objects.count(), 1)

        staff = User.objects.create_user("staff@example.com", role="staff")
        self.client.force_authenticate(staff)
        self.assertEqual(self.client.get(target_url).status_code, 404)
        self.assertEqual(self.client.post(endpoint, {"event_id": str(target.pk)}, format="json").status_code, 403)
        google.return_value["visibility"] = "private"
        self.assertEqual(self.client.get(endpoint).status_code, 404)

    def test_manual_tasks_are_idempotent_and_admin_only(self):
        from uuid import uuid4

        staff = User.objects.create_user("assignee@example.com", role="staff")
        body = {
            "request_id": str(uuid4()),
            "title": "Review the venue proposal",
            "assignee": str(staff.pk),
            "status": "in_progress",
        }
        response = self.client.post("/api/team-tasks/", body, format="json")
        self.assertEqual(response.status_code, 201)
        retry = self.client.post("/api/team-tasks/", body, format="json")
        self.assertEqual(retry.status_code, 200)
        self.assertEqual(retry.data["id"], response.data["id"])
        task = TeamTask.objects.get()
        self.assertIsNone(task.meeting_link_id)
        self.assertEqual(task.assignee, staff)
        self.client.force_authenticate(staff)
        self.assertEqual(self.client.post("/api/team-tasks/", body, format="json").status_code, 403)

    def test_meeting_suggestions_rank_partial_and_client_matches_and_offer_browse_fallback(self):
        from Events.models import Event
        from Staff.meeting_event_links import candidates

        Event.objects.create(name="Antrah Wellness Festival, Mumbai", client_name="Antrah")
        Event.objects.create(name="Product Launch", client_name="HydRo365")
        Event.objects.create(name="Festival Planning")
        result = candidates({"summary": "Antrah Wellness Festival X HydRo365"}, Event.objects.all(), "")
        self.assertEqual([event["name"] for event in result], [
            "Antrah Wellness Festival, Mumbai", "Product Launch",
        ])
        self.assertTrue(all(event["suggested"] for event in result))
        fallback = candidates({"summary": "Daily sync"}, Event.objects.all(), "")
        self.assertEqual(len(fallback), 3)
        self.assertFalse(any(event["suggested"] for event in fallback))
