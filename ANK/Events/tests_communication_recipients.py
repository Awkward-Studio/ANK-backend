from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from Events.models.event_model import Event
from Events.models.event_registration_model import EventRegistration
from Events.models.session_model import Session
from Events.models.session_registration import SessionRegistration
from Guest.models import Guest
from Staff.models import User


class CommunicationRecipientRegistrationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            email="communications@example.com",
            password="password123",
            role="admin",
            name="Communications Admin",
        )
        self.client.force_authenticate(user=self.admin)
        self.event = Event.objects.create(name="Wedding", type="wedding")
        self.function = Session.objects.create(event=self.event, title="Sangeet")
        self.url = "/api/events/communication-recipients/"

    def test_creates_guest_event_and_function_registrations(self):
        response = self.client.post(
            self.url,
            {
                "name": "Asha Rao",
                "phone": "98765 43210",
                "event_id": str(self.event.id),
                "session_id": str(self.function.id),
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        guest = Guest.objects.get(phone="+919876543210")
        event_registration = EventRegistration.objects.get(guest=guest, event=self.event)
        session_registration = SessionRegistration.objects.get(guest=guest, session=self.function)
        self.assertEqual(response.data["guest"]["id"], str(guest.id))
        self.assertEqual(response.data["event_registration"]["id"], str(event_registration.id))
        self.assertEqual(response.data["session_registration"]["id"], str(session_registration.id))

    def test_reuses_existing_records_for_same_phone(self):
        guest = Guest.objects.create(name="Asha Rao", phone="+91 98765-43210")
        event_registration = EventRegistration.objects.create(guest=guest, event=self.event)
        session_registration = SessionRegistration.objects.create(guest=guest, session=self.function)

        response = self.client.post(
            self.url,
            {
                "name": "Asha Rao",
                "phone": "+919876543210",
                "event_id": str(self.event.id),
                "session_id": str(self.function.id),
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Guest.objects.count(), 1)
        self.assertEqual(EventRegistration.objects.count(), 1)
        self.assertEqual(SessionRegistration.objects.count(), 1)
        self.assertEqual(response.data["event_registration"]["id"], str(event_registration.id))
        self.assertEqual(response.data["session_registration"]["id"], str(session_registration.id))

    def test_rejects_function_from_another_event(self):
        other_event = Event.objects.create(name="Conference", type="corporate")
        other_function = Session.objects.create(event=other_event, title="Keynote")

        response = self.client.post(
            self.url,
            {
                "name": "Asha Rao",
                "phone": "+919876543210",
                "event_id": str(self.event.id),
                "session_id": str(other_function.id),
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Guest.objects.count(), 0)

    def test_event_only_recipient_omits_function_registration(self):
        response = self.client.post(
            self.url,
            {
                "name": "Asha Rao",
                "phone": "+919876543210",
                "event_id": str(self.event.id),
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIsNone(response.data["session"])
        self.assertIsNone(response.data["session_registration"])
        self.assertEqual(SessionRegistration.objects.count(), 0)
