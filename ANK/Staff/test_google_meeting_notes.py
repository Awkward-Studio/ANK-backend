from datetime import timedelta
from unittest.mock import patch
from urllib.parse import quote

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from Staff.google_calendar_service import EVENT_SCOPE, cipher
from Staff.google_meeting_notes import NOTES_SCOPES
from Staff.models import GoogleCalendarConnection, User


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
