from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from Staff.google_calendar_service import EVENT_SCOPE, CalendarError, cipher
from Staff.models import (
    GoogleCalendarConnection,
    GoogleCalendarMeeting,
    GoogleCalendarOAuthAttempt,
    User,
)


BASE = "/api/team-calendar/"
CALLBACK = "/api/auth/google/calendar/callback/"
CALENDAR = "tests@group.calendar.google.com"
ACCOUNT = "calendar@example.com"
APP = "https://ank.example.com"


@override_settings(
    GOOGLE_CALENDAR_CLIENT_ID="test-client",
    GOOGLE_CALENDAR_CLIENT_SECRET="test-secret",
    GOOGLE_CALENDAR_ID=CALENDAR,
    GOOGLE_CALENDAR_ACCOUNT_EMAIL=ACCOUNT,
    GOOGLE_CALENDAR_APP_ORIGIN=APP,
)
class GoogleCalendarTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user("admin@example.com", role="admin")
        cls.other_admin = User.objects.create_user("other@example.com", role="admin")
        cls.head = User.objects.create_user("head@example.com", role="department_head")
        cls.staff = User.objects.create_user("staff@example.com", role="staff")

    def setUp(self):
        self.client = APIClient()

    def start_callback(self):
        self.client.force_authenticate(self.admin)
        start = self.client.post(BASE + "connect/", HTTP_ORIGIN=APP)
        self.assertEqual(start.status_code, 200)
        attempt = start.json()
        query = parse_qs(urlsplit(attempt["authorization_url"]).query)
        self.assertEqual(query["code_challenge_method"], ["S256"])
        self.assertIn(EVENT_SCOPE, query["scope"][0].split())
        response = self.client.get(CALLBACK, {"state": attempt["state"], "code": "test-code"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], f"{APP}/team-calendar#google={attempt['state']}")
        self.assertNotIn("test-code", response["Location"])
        return {key: attempt[key] for key in ("state", "verifier")}

    @patch("Staff.google_calendar.calendar_request", return_value={"accessRole": "writer"})
    @patch("Staff.google_calendar.google_request", return_value={
        "email": ACCOUNT, "email_verified": True,
    })
    @patch("Staff.google_calendar.token_request", return_value={
        "access_token": "access", "refresh_token": "refresh", "scope": EVENT_SCOPE,
    })
    def test_connect_requires_same_admin_and_browser_verifier(self, exchange, _identity, calendar):
        attempt = self.start_callback()
        self.client.force_authenticate(self.other_admin)
        self.assertEqual(self.client.post(BASE + "connect/complete/", attempt).status_code, 400)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.post(
            BASE + "connect/complete/", {**attempt, "verifier": "a" * 64}
        ).status_code, 400)
        exchange.assert_not_called()

        self.assertEqual(self.client.post(BASE + "connect/complete/", attempt).status_code, 200)
        saved = GoogleCalendarConnection.objects.get(calendar_id=CALENDAR)
        self.assertNotEqual(saved.refresh_token, "refresh")
        self.assertEqual(cipher().decrypt(saved.refresh_token.encode()).decode(), "refresh")
        self.assertEqual(exchange.call_args.kwargs["code_verifier"], attempt["verifier"])
        self.assertEqual(calendar.call_args.args, ("GET", "access"))
        self.assertFalse(GoogleCalendarOAuthAttempt.objects.exists())
        self.assertEqual(self.client.post(BASE + "connect/complete/", attempt).status_code, 400)
        self.assertEqual(exchange.call_count, 1)

    @patch("Staff.google_calendar.calendar_request")
    @patch("Staff.google_calendar.google_request", return_value={
        "email": "wrong@example.com", "email_verified": True,
    })
    @patch("Staff.google_calendar.token_request", return_value={
        "access_token": "access", "refresh_token": "refresh", "scope": EVENT_SCOPE,
    })
    def test_connect_rejects_wrong_google_account(self, _exchange, _identity, calendar):
        attempt = self.start_callback()
        self.assertEqual(self.client.post(BASE + "connect/complete/", attempt).status_code, 403)
        calendar.assert_not_called()
        self.assertFalse(GoogleCalendarConnection.objects.exists())

    def test_oauth_start_is_admin_only(self):
        self.client.force_authenticate(self.head)
        self.assertEqual(self.client.post(BASE + "connect/").status_code, 403)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.post(
            BASE + "connect/", HTTP_ORIGIN="https://other.example.com"
        ).status_code, 400)

    @patch("Staff.google_calendar.access_token", return_value="access")
    @patch("Staff.google_calendar.calendar_request")
    def test_staff_sees_private_events_as_busy_and_cannot_create(self, calendar, _token):
        self.client.force_authenticate(self.staff)
        calendar.return_value = {"items": [
            {
                "id": "private", "summary": "Sensitive", "description": "Secret",
                "visibility": "private", "start": {"date": "2026-11-20"},
                "end": {"date": "2026-11-21"}, "attendees": [{"email": ACCOUNT}],
            },
            {"id": "cancelled", "status": "cancelled"},
        ]}
        result = self.client.get(BASE + "events/", {
            "start": "2026-11-01T00:00:00Z", "end": "2026-12-01T00:00:00Z",
        })
        self.assertEqual(result.status_code, 200)
        [event] = result.json()["events"]
        self.assertEqual(event["summary"], "Busy")
        self.assertEqual(event["attendees"], [])
        self.assertNotContains(result, "Sensitive")
        self.assertEqual(self.client.post(BASE + "events/").status_code, 403)
        self.assertEqual(calendar.call_count, 1)

    @patch("Staff.google_calendar.access_token", return_value="access")
    @patch("Staff.google_calendar.calendar_request")
    def test_create_retry_returns_same_event_and_only_creator_can_manage(self, calendar, _token):
        self.client.force_authenticate(self.head)
        request_id = uuid4()
        path = BASE + f"events/{request_id.hex}/"
        fields = {
            "summary": "Client review", "start": "2026-11-20T10:00:00+05:30",
            "end": "2026-11-20T11:00:00+05:30", "request_id": str(request_id),
        }
        event = {}

        def google(method, _token, event_id=None, **kwargs):
            if method == "POST":
                self.assertEqual(kwargs["params"], {"sendUpdates": "all"})
                if event:
                    raise CalendarError("Already exists", 409)
                event.update(kwargs["json"], organizer={"self": True}, etag='"v1"')
            elif method == "DELETE":
                self.assertEqual(kwargs["headers"], {"If-Match": '"v1"'})
                self.assertEqual(kwargs["params"], {"sendUpdates": "all"})
            if event_id:
                self.assertEqual(event_id, request_id.hex)
            return event

        calendar.side_effect = google
        first = self.client.post(BASE + "events/", fields, format="json")
        second = self.client.post(BASE + "events/", fields, format="json")
        self.assertEqual(first.status_code, 201)
        self.assertEqual(first.json(), second.json())
        self.assertTrue(first.json()["can_manage"])
        self.assertEqual(GoogleCalendarMeeting.objects.count(), 1)

        self.client.force_authenticate(self.staff)
        self.assertEqual(self.client.delete(path, HTTP_IF_MATCH='"v1"').status_code, 403)
        self.client.force_authenticate(self.head)
        self.assertEqual(self.client.delete(path, HTTP_IF_MATCH='"old"').status_code, 412)
        self.assertEqual(self.client.delete(path, HTTP_IF_MATCH='"v1"').status_code, 204)

    @patch("Staff.google_calendar.access_token", return_value="access")
    @patch("Staff.google_calendar.calendar_request")
    def test_a_google_event_cannot_be_claimed_with_its_event_id(self, calendar, _token):
        self.client.force_authenticate(self.head)
        event_id = uuid4()
        calendar.side_effect = [
            CalendarError("Already exists", 409),
            {
                "id": event_id.hex,
                "summary": "Written directly in Google Calendar",
                "organizer": {"self": True},
                "start": {"dateTime": "2026-11-20T04:30:00Z"},
                "etag": '"v1"',
            },
        ]
        response = self.client.post(BASE + "events/", {
            "summary": "Attempt to claim a Google event",
            "start": "2026-11-20T04:30:00Z",
            "end": "2026-11-20T05:30:00Z",
            "request_id": str(event_id),
        }, format="json")
        self.assertEqual(response.status_code, 409)
        calendar.side_effect = None
        calendar.return_value = {
            "id": event_id.hex,
            "organizer": {"self": True},
            "start": {"dateTime": "2026-11-20T04:30:00Z"},
            "etag": '"v1"',
        }
        self.assertEqual(self.client.delete(
            BASE + f"events/{event_id.hex}/", HTTP_IF_MATCH='"v1"'
        ).status_code, 403)
        self.assertEqual(calendar.call_count, 3)
