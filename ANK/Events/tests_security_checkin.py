import uuid
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from Events.models.event_model import Event
from Events.models.event_registration_model import EventRegistration
from Events.models.session_model import Session
from Events.models.session_registration import SessionRegistration
from Guest.models import Guest
from Staff.models import User
from MessageTemplates.temporary_tools.qr_test_media import encrypt_security_qr_payload


class SecurityCheckInTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Users with different roles
        self.security_user = User.objects.create_user(
            email="security@example.com",
            password="password123",
            role="security",
            name="Security Guard",
        )
        self.admin_user = User.objects.create_user(
            email="admin@example.com",
            password="password123",
            role="admin",
            name="Admin User",
        )
        self.staff_user = User.objects.create_user(
            email="staff@example.com",
            password="password123",
            role="staff",
            name="Staff User",
        )

        # Event
        self.event = Event.objects.create(
            name="Sharma Wedding",
            type="wedding",
            location="Udaipur",
            venue="The Leela Palace",
            bride_name="Pooja",
            groom_name="Rahul",
        )

        # Functions / Sessions
        self.sangeet = Session.objects.create(
            event=self.event,
            title="Sangeet Ceremony",
            venue_name="Grand Ballroom",
            start_time=timezone.now(),
        )
        self.reception = Session.objects.create(
            event=self.event,
            title="Wedding Reception",
            venue_name="Lakeside Lawn",
            start_time=timezone.now(),
        )

        # Guest
        self.guest = Guest.objects.create(
            name="Amit Patel",
            email="amit.patel@example.com",
            phone="+919876543210",
            city="Mumbai",
        )

        # EventRegistration
        self.event_reg = EventRegistration.objects.create(
            guest=self.guest,
            event=self.event,
            uid="ANK-G-001",
            rsvp_status="yes",
            guest_group="Family",
            estimated_pax=2,
            is_checked_in=False,
        )

        # SessionRegistrations
        self.sreg_sangeet = SessionRegistration.objects.create(
            guest=self.guest,
            session=self.sangeet,
            is_checked_in=False,
        )
        self.sreg_reception = SessionRegistration.objects.create(
            guest=self.guest,
            session=self.reception,
            is_checked_in=False,
        )

        # Generate encrypted QR token for this registration
        self.valid_payload = {
            "type": "ank_dynamic_qr_test",
            "test_id": str(uuid.uuid4()),
            "registration_id": str(self.event_reg.id),
            "event_id": str(self.event.id),
            "recipient": {
                "name": self.guest.name,
                "phone": self.guest.phone,
            },
            "data": {
                "Gate": "Main Gate",
                "Table": "T-12",
            },
        }
        self.valid_token = encrypt_security_qr_payload(self.valid_payload)

    def test_verify_pass_requires_authorization(self):
        # 1. Unauthenticated request
        res = self.client.post("/api/events/security/verify-pass/", {"token": self.valid_token})
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

        # 2. Staff user (not security or admin)
        self.client.force_authenticate(user=self.staff_user)
        res = self.client.post("/api/events/security/verify-pass/", {"token": self.valid_token})
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_verify_pass_success_security_user(self):
        self.client.force_authenticate(user=self.security_user)
        res = self.client.post("/api/events/security/verify-pass/", {"token": self.valid_token})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        self.assertTrue(data["ok"])
        self.assertTrue(data["valid"])
        self.assertFalse(data["already_checked_in"])
        self.assertIsNone(data["checked_in_at"])
        self.assertEqual(data["guest"]["name"], "Amit Patel")
        self.assertEqual(data["guest"]["phone"], "+919876543210")
        self.assertEqual(data["event"]["name"], "Sharma Wedding")
        self.assertEqual(data["registration"]["rsvp_status"], "yes")
        self.assertEqual(len(data["all_sessions"]), 2)

    @override_settings(DJANGO_RSVP_SECRET="test-shared-secret")
    def test_verify_pass_accepts_shared_secret_without_jwt(self):
        self.client.force_authenticate(user=None)
        self.client.credentials(
            HTTP_X_WEBHOOK_TOKEN="test-shared-secret",
            HTTP_X_USER_ROLE="security",
            HTTP_X_USER_EMAIL="gate@example.com",
        )

        res = self.client.post("/api/events/security/verify-pass/", {"token": self.valid_token})

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.json()["valid"])

    @override_settings(DJANGO_RSVP_SECRET="test-shared-secret")
    def test_check_in_accepts_shared_secret_without_jwt(self):
        self.client.force_authenticate(user=None)
        self.client.credentials(
            HTTP_X_WEBHOOK_TOKEN="test-shared-secret",
            HTTP_X_USER_ROLE="security",
            HTTP_X_USER_EMAIL="gate@example.com",
        )

        res = self.client.post(
            "/api/events/security/check-in/",
            {"token": self.valid_token, "registration_id": str(self.event_reg.id)},
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.json()["ok"])

    def test_verify_pass_invalid_or_tampered_token(self):
        self.client.force_authenticate(user=self.security_user)
        tampered = self.valid_token[:-6] + "XXXXXX"
        res = self.client.post("/api/events/security/verify-pass/", {"token": tampered})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        self.assertFalse(data["valid"])
        self.assertIn("Corrupted", data["error"])

    def test_verify_pass_unregistered_guest(self):
        self.client.force_authenticate(user=self.security_user)
        non_existent_payload = {
            "type": "ank_dynamic_qr_test",
            "test_id": str(uuid.uuid4()),
            "registration_id": str(uuid.uuid4()),
            "recipient": {"name": "Ghost Guest", "phone": "+910000000000"},
        }
        token = encrypt_security_qr_payload(non_existent_payload)
        res = self.client.post("/api/events/security/verify-pass/", {"token": token})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        self.assertFalse(data["valid"])
        self.assertIn("No matching guest registration", data["error"])

    def test_check_in_success_and_stored_in_database(self):
        self.client.force_authenticate(user=self.security_user)
        res = self.client.post("/api/events/security/check-in/", {
            "token": self.valid_token,
            "registration_id": str(self.event_reg.id),
        })
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        self.assertTrue(data["ok"])
        self.assertTrue(data["success"])
        self.assertTrue(data["is_checked_in"])
        self.assertIsNotNone(data["checked_in_at"])

        # Verify database record updated
        self.event_reg.refresh_from_db()
        self.assertTrue(self.event_reg.is_checked_in)
        self.assertIsNotNone(self.event_reg.checked_in_at)
        self.assertEqual(self.event_reg.checked_in_by, self.security_user)

    def test_duplicate_check_in_rejected_with_409_and_timestamp(self):
        self.client.force_authenticate(user=self.security_user)

        # 1. First check-in
        res1 = self.client.post("/api/events/security/check-in/", {
            "token": self.valid_token,
            "registration_id": str(self.event_reg.id),
        })
        self.assertEqual(res1.status_code, status.HTTP_200_OK)
        first_timestamp = res1.json()["checked_in_at"]

        # 2. Second check-in attempt with same QR code
        res2 = self.client.post("/api/events/security/check-in/", {
            "token": self.valid_token,
            "registration_id": str(self.event_reg.id),
        })
        self.assertEqual(res2.status_code, status.HTTP_409_CONFLICT)
        data2 = res2.json()
        self.assertFalse(data2["ok"])
        self.assertTrue(data2["already_checked_in"])
        self.assertEqual(data2["error"], "Guest has already checked in.")
        self.assertEqual(data2["checked_in_at"], first_timestamp)

    def test_function_specific_check_in(self):
        self.client.force_authenticate(user=self.security_user)

        # Check in specifically to Sangeet
        res = self.client.post("/api/events/security/check-in/", {
            "token": self.valid_token,
            "registration_id": str(self.event_reg.id),
            "session_id": str(self.sangeet.id),
        })
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        self.sreg_sangeet.refresh_from_db()
        self.sreg_reception.refresh_from_db()
        self.event_reg.refresh_from_db()

        # Sangeet is attended
        self.assertTrue(self.sreg_sangeet.is_checked_in)
        # Reception is NOT attended yet
        self.assertFalse(self.sreg_reception.is_checked_in)
        # Event is also marked attended
        self.assertTrue(self.event_reg.is_checked_in)

        # Duplicate check-in to Sangeet is rejected
        res_dup = self.client.post("/api/events/security/check-in/", {
            "token": self.valid_token,
            "registration_id": str(self.event_reg.id),
            "session_id": str(self.sangeet.id),
        })
        self.assertEqual(res_dup.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("Sangeet Ceremony", res_dup.json()["error"])

        # Check-in to Reception should succeed
        res_rec = self.client.post("/api/events/security/check-in/", {
            "token": self.valid_token,
            "registration_id": str(self.event_reg.id),
            "session_id": str(self.reception.id),
        })
        self.assertEqual(res_rec.status_code, status.HTTP_200_OK)
        self.sreg_reception.refresh_from_db()
        self.assertTrue(self.sreg_reception.is_checked_in)

    def test_forged_registration_id_mismatch_rejected(self):
        self.client.force_authenticate(user=self.security_user)
        # Pass legitimate token for Amit Patel, but forged registration_id
        res = self.client.post("/api/events/security/check-in/", {
            "token": self.valid_token,
            "registration_id": str(uuid.uuid4()),
        })
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("mismatch", res.json()["error"])

    def test_rapid_consecutive_check_ins(self):
        # Verify that rapid consecutive check-in calls are safely handled
        # and only the first check-in updates the record while subsequent calls return 409
        self.client.force_authenticate(user=self.security_user)
        res1 = self.client.post("/api/events/security/check-in/", {
            "token": self.valid_token,
            "registration_id": str(self.event_reg.id),
        })
        self.assertEqual(res1.status_code, status.HTTP_200_OK)

        res2 = self.client.post("/api/events/security/check-in/", {
            "token": self.valid_token,
            "registration_id": str(self.event_reg.id),
        })
        self.assertEqual(res2.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(res2.json()["error"], "Guest has already checked in.")

        res3 = self.client.post("/api/events/security/check-in/", {
            "token": self.valid_token,
            "registration_id": str(self.event_reg.id),
        })
        self.assertEqual(res3.status_code, status.HTTP_409_CONFLICT)


