import json
from unittest.mock import MagicMock, patch

from django.urls import reverse
from rest_framework.test import APITestCase

from MessageTemplates.models import WhatsAppPhoneNumber
from MessageTemplates.temporary_tools.qr_test_media import (
    SECURITY_TOKEN_PREFIX,
    decrypt_security_qr_payload,
    encrypt_security_qr_payload,
)


@patch.dict("os.environ", {"DJANGO_RSVP_SECRET": "qr-test-secret"}, clear=False)
class DynamicQRCodeTestMediaTests(APITestCase):
    def setUp(self):
        self.client.credentials(HTTP_X_WEBHOOK_TOKEN="qr-test-secret")
        self.qr_sender = WhatsAppPhoneNumber.objects.create(
            phone_number_id="hr-sender",
            asset_id="hr-asset",
            waba_id="hr-waba",
            display_phone_number="+91 90000 00792",
            verified_name="ANK HR",
            is_active=True,
        )

    @patch("MessageTemplates.temporary_tools.qr_test_media._upload_qr_to_meta", return_value="test-media-id")
    @patch("MessageTemplates.temporary_tools.qr_test_media._qr_png", return_value=MagicMock())
    @patch("MessageTemplates.temporary_tools.qr_test_media._get_credentials", return_value=("meta-token", "hr-sender"))
    def test_security_encrypted_qr_is_unique_and_viewable_only_by_security_module(self, credentials, qr_png, upload):
        request_payload = {
            "recipient_name": "Test Guest",
            "recipient_phone": "919876543210",
            "sender_phone_number_id": "hr-sender",
            "template_name": "qr_image_bulksend_test",
            "details": {"Gate": "North", "Seat": "A-12"},
        }

        first = self.client.post(reverse("whatsapp-qr-test-media"), request_payload, format="json")
        first_encoded = qr_png.call_args.args[0]
        second = self.client.post(reverse("whatsapp-qr-test-media"), request_payload, format="json")
        second_encoded = qr_png.call_args.args[0]

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)

        # Ensure the QR does NOT contain raw JSON (cannot be viewed by ordinary phone camera / QR scanners)
        self.assertTrue(first_encoded.startswith(SECURITY_TOKEN_PREFIX))
        self.assertTrue(second_encoded.startswith(SECURITY_TOKEN_PREFIX))
        self.assertNotIn("919876543210", first_encoded)
        self.assertNotIn("Test Guest", first_encoded)
        self.assertNotIn("North", first_encoded)

        # Ensure only the security module can decrypt and view it
        first_decrypted = decrypt_security_qr_payload(first_encoded)
        second_decrypted = decrypt_security_qr_payload(second_encoded)
        self.assertEqual(first_decrypted["recipient"]["phone"], "919876543210")
        self.assertEqual(first_decrypted["recipient"]["name"], "Test Guest")
        self.assertEqual(first_decrypted["data"], {"Gate": "North", "Seat": "A-12"})
        self.assertNotEqual(first_decrypted["test_id"], second_decrypted["test_id"])
        self.assertNotEqual(first_decrypted["random_code"], second_decrypted["random_code"])

        # Test verification endpoint
        verify_res = self.client.post(
            reverse("whatsapp-qr-test-media-verify"),
            {"token": first_encoded},
            format="json",
        )
        self.assertEqual(verify_res.status_code, 200)
        self.assertTrue(verify_res.json()["ok"])
        self.assertTrue(verify_res.json()["valid"])
        self.assertEqual(verify_res.json()["payload"]["recipient"]["name"], "Test Guest")

        # Test invalid / tampered token verification
        tampered = first_encoded[:-4] + "AAAA"
        verify_tampered = self.client.post(
            reverse("whatsapp-qr-test-media-verify"),
            {"token": tampered},
            format="json",
        )
        self.assertEqual(verify_tampered.status_code, 200)
        self.assertFalse(verify_tampered.json()["valid"])

        blocked_sender = WhatsAppPhoneNumber.objects.create(
            phone_number_id="other-sender",
            asset_id="other-asset",
            waba_id="other-waba",
            display_phone_number="+91 90000 00123",
            verified_name="Other",
            is_active=True,
        )
        blocked_payload = {**request_payload, "sender_phone_number_id": blocked_sender.phone_number_id}
        blocked = self.client.post(reverse("whatsapp-qr-test-media"), blocked_payload, format="json")
        self.assertEqual(blocked.status_code, 403)

