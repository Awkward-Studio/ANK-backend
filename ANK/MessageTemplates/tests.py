from unittest.mock import patch

from django.urls import reverse
from rest_framework.test import APITestCase

from MessageTemplates.models import WhatsAppBusinessAccount, WhatsAppPhoneNumber
from MessageTemplates.serializers import WhatsAppPhoneNumberSerializer
from MessageTemplates.services.hosted_reconciliation import apply_comparison
from Staff.models import User


class HostedReconciliationApiTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(email="admin@example.com", password="password", role="admin")
        self.staff = User.objects.create_user(email="staff@example.com", password="password", role="staff")
        self.preview_url = reverse("whatsapp-reconciliation-preview")
        self.apply_url = reverse("whatsapp-reconciliation-apply")
        self.snapshot_url = reverse("whatsapp-reconciliation-snapshot")

    def test_staff_cannot_access_snapshot(self):
        self.client.force_authenticate(self.staff)
        self.assertEqual(self.client.get(self.snapshot_url).status_code, 403)

    def test_admin_can_access_snapshot(self):
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get(self.snapshot_url).status_code, 200)

    @patch("MessageTemplates.whatsapp_views.hosted_reconciliation.build_comparison")
    def test_preview_never_echoes_access_token(self, comparison_mock):
        comparison_mock.return_value = ({"graph_api_version": "v25.0", "wabas": [], "summary": {}}, "a" * 64)
        self.client.force_authenticate(self.admin)
        token = "temporary-meta-token-value"
        response = self.client.post(self.preview_url, {"access_token": token}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(token, response.content.decode())

    @patch("MessageTemplates.whatsapp_views.hosted_reconciliation.build_comparison")
    def test_apply_rejects_changed_digest(self, comparison_mock):
        comparison_mock.return_value = ({"graph_api_version": "v25.0", "wabas": [], "summary": {}}, "b" * 64)
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            self.apply_url,
            {"access_token": "temporary-meta-token-value", "comparison_digest": "a" * 64},
            format="json",
        )
        self.assertEqual(response.status_code, 409)


class HostedReconciliationApplyTests(APITestCase):
    def setUp(self):
        self.waba = WhatsAppBusinessAccount.objects.create(waba_id="waba-1", name="WABA")
        self.phone = WhatsAppPhoneNumber.objects.create(
            business_account=self.waba,
            phone_number_id="phone-1",
            asset_id="asset-1",
            waba_id="waba-1",
            display_phone_number="+910000000000",
            verified_name="Old Name",
            name_status="APPROVED",
            is_active=True,
            is_default=True,
        )

    def test_apply_updates_meta_fields_but_preserves_structure(self):
        comparison = {
            "wabas": [
                {
                    "waba_id": "waba-1",
                    "error": None,
                    "phones": [
                        {
                            "classification": "field_mismatch",
                            "phone_number_id": "phone-1",
                            "meta": {"display_phone_number": "+911111111111", "verified_name": "Meta Name", "quality_rating": "GREEN", "code_verification_status": "VERIFIED", "name_status": None, "platform_type": "CLOUD_API"},
                            "unavailable_fields": [],
                        },
                        {
                            "classification": "meta_only",
                            "phone_number_id": "phone-2",
                            "meta": {"display_phone_number": "+922222222222"},
                            "unavailable_fields": [],
                        },
                    ],
                }
            ]
        }
        apply_comparison(comparison)
        self.phone.refresh_from_db()
        self.assertEqual(self.phone.verified_name, "Meta Name")
        self.assertEqual(self.phone.code_verification_status, "VERIFIED")
        self.assertEqual(self.phone.name_status, "")
        self.assertEqual(self.phone.platform_type, "CLOUD_API")
        self.assertTrue(self.phone.is_usable)
        self.assertEqual(self.phone.waba_id, "waba-1")
        self.assertTrue(self.phone.is_active)
        self.assertTrue(self.phone.is_default)
        self.assertFalse(WhatsAppPhoneNumber.objects.filter(phone_number_id="phone-2").exists())

    def test_non_cloud_platform_is_not_usable(self):
        self.phone.platform_type = "ON_PREMISE"
        self.phone.save(update_fields=["platform_type"])

        self.assertFalse(self.phone.is_usable)
        self.assertIn("not CLOUD_API", self.phone.usability_reason)
        serialized = WhatsAppPhoneNumberSerializer(self.phone).data
        self.assertFalse(serialized["is_usable"])
        self.assertEqual(serialized["platform_type"], "ON_PREMISE")

    def test_failed_waba_preserves_last_snapshot(self):
        self.phone.meta_details_snapshot = {"quality_rating": "GREEN"}
        self.phone.save(update_fields=["meta_details_snapshot"])
        comparison = {
            "wabas": [
                {
                    "waba_id": "waba-1",
                    "error": {"message": "Permission denied", "code": 200, "access_state": "access_denied"},
                    "phones": [],
                }
            ]
        }
        apply_comparison(comparison)
        self.phone.refresh_from_db()
        self.assertEqual(self.phone.meta_details_snapshot, {"quality_rating": "GREEN"})
        self.assertEqual(self.phone.meta_access_state, "access_denied")
