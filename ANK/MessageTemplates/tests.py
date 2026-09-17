from unittest.mock import patch

from django.core.cache import cache
from django.urls import reverse
from django.test import SimpleTestCase
from rest_framework.test import APITestCase

from MessageTemplates.models import WhatsAppBusinessAccount, WhatsAppPhoneNumber
from MessageTemplates.serializers import WhatsAppPhoneNumberSerializer, WhatsAppPhoneNumberWriteSerializer
from MessageTemplates.services.hosted_reconciliation import apply_comparison
from MessageTemplates.services.meta_reconciliation import (
    _subscription_audit,
    _token_audit,
    phone_identity_verification,
)
from Staff.models import User


class MetaIdentityVerificationTests(SimpleTestCase):
    def test_nonexistent_name_is_not_approved(self):
        result = phone_identity_verification(
            {
                "verified_name": "Tanisha & Tushar RSVP",
                "name_status": "NON_EXISTS",
                "new_name_status": "NONE",
                "platform_type": "CLOUD_API",
                "is_on_biz_app": True,
            }
        )

        self.assertFalse(result["display_name_approved"])
        self.assertEqual(result["display_name_status"], "NON_EXISTS")
        self.assertTrue(result["coexistence_confirmed"])

    def test_approved_name_and_coexistence_are_independent_verdicts(self):
        result = phone_identity_verification(
            {
                "verified_name": "A New Knot",
                "name_status": "APPROVED",
                "platform_type": "CLOUD_API",
                "is_on_biz_app": False,
            }
        )

        self.assertTrue(result["display_name_approved"])
        self.assertFalse(result["coexistence_confirmed"])

    @patch.dict("os.environ", {"META_APP_ID": "app-1", "META_APP_ACCESS_TOKEN": "app-secret-token"}, clear=False)
    @patch("MessageTemplates.services.meta_reconciliation._meta_get")
    def test_token_audit_is_sanitized(self, meta_get):
        meta_get.return_value = (
            {
                "data": {
                    "is_valid": True,
                    "app_id": "app-1",
                    "scopes": ["whatsapp_business_management", "whatsapp_business_messaging"],
                    "granular_scopes": [{"scope": "whatsapp_business_management", "target_ids": ["waba-1"]}],
                }
            },
            {},
        )

        result = _token_audit("never-return-this-token", "waba-1")

        self.assertEqual(result["status"], "valid")
        self.assertTrue(result["app_matches"])
        self.assertTrue(result["required_scopes_granted"])
        self.assertTrue(result["waba_in_granular_targets"])
        self.assertNotIn("never-return-this-token", str(result))

    @patch.dict("os.environ", {"META_APP_ID": "app-1"}, clear=False)
    @patch("MessageTemplates.services.meta_reconciliation._meta_get")
    def test_subscription_audit_supports_meta_nested_app_shape(self, meta_get):
        meta_get.return_value = (
            {
                "data": [
                    {"whatsapp_business_api_data": {"id": "app-1", "name": "ANK"}}
                ]
            },
            {},
        )

        result = _subscription_audit("waba-1", "never-return-this-token")

        self.assertEqual(result["status"], "verified")
        self.assertTrue(result["subscribed"])
        self.assertEqual(result["apps"], [{"id": "app-1", "name": "ANK"}])
        self.assertNotIn("never-return-this-token", str(result))


class MetaStatusApiIdentityTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.waba = WhatsAppBusinessAccount.objects.create(waba_id="waba-status", name="RSVP WABA")
        self.phone = WhatsAppPhoneNumber.objects.create(
            business_account=self.waba,
            phone_number_id="phone-status",
            asset_id="phone-status",
            waba_id="waba-status",
            display_phone_number="+919920928992",
            verified_name="Tanisha & Tushar RSVP",
        )

    @patch("MessageTemplates.whatsapp_views.waba_management.WEBHOOK_SECRET", "status-secret")
    @patch("MessageTemplates.whatsapp_views.waba_management.reconcile_all_wabas")
    def test_status_response_exposes_explicit_identity_verdict_without_tokens(self, reconcile):
        reconcile.return_value = [
            {
                "waba_id": "waba-status",
                "fetch_error": "",
                "numbers": [self.phone],
                "meta_phone_number_ids": ["phone-status"],
                "meta_details_by_phone_id": {
                    "phone-status": {
                        "verified_name": "Tanisha & Tushar RSVP",
                        "name_status": "NON_EXISTS",
                        "new_name_status": "NONE",
                        "platform_type": "CLOUD_API",
                        "is_on_biz_app": True,
                    }
                },
                "template_management": {"status": "available", "reason": ""},
                "verification": {
                    "token_source": "production_environment",
                    "token": {"status": "valid", "app_id": "app-1"},
                    "app_subscription": {"status": "verified", "subscribed": True},
                },
            }
        ]

        response = self.client.get(
            "/api/whatsapp/meta-status/",
            HTTP_X_WEBHOOK_TOKEN="status-secret",
        )

        self.assertEqual(response.status_code, 200)
        number = response.data["wabas"][0]["numbers"][0]
        self.assertFalse(number["identity_verification"]["display_name_approved"])
        self.assertEqual(number["identity_verification"]["display_name_status"], "NON_EXISTS")
        self.assertTrue(number["identity_verification"]["coexistence_confirmed"])
        self.assertNotIn("access_token", str(response.data).lower())

        cached_response = self.client.get(
            "/api/whatsapp/meta-status/",
            HTTP_X_WEBHOOK_TOKEN="status-secret",
        )
        self.assertEqual(cached_response.status_code, 200)
        self.assertTrue(cached_response.data["cache"]["hit"])
        reconcile.assert_called_once()

        refreshed_response = self.client.get(
            "/api/whatsapp/meta-status/?force_refresh=true",
            HTTP_X_WEBHOOK_TOKEN="status-secret",
        )
        self.assertEqual(refreshed_response.status_code, 200)
        self.assertFalse(refreshed_response.data["cache"]["hit"])
        self.assertEqual(reconcile.call_count, 2)


class DisplayNameManagementApiTests(APITestCase):
    def setUp(self):
        self.waba = WhatsAppBusinessAccount.objects.create(waba_id="waba-display", name="Display WABA")
        self.phone = WhatsAppPhoneNumber.objects.create(
            business_account=self.waba,
            phone_number_id="phone-display",
            asset_id="phone-display",
            waba_id="waba-display",
            display_phone_number="+919920928992",
            verified_name="Tanisha & Tushar's Hospitality Team",
            is_active=True,
        )
        self.url = reverse("whatsapp-phone-display-name", args=[self.phone.phone_number_id])

    @patch("MessageTemplates.whatsapp_views.waba_management.WEBHOOK_SECRET", "status-secret")
    @patch("MessageTemplates.whatsapp_views.waba_management.fetch_phone_display_name_status")
    @patch("MessageTemplates.whatsapp_views.waba_management.submit_phone_display_name")
    def test_submit_display_name_returns_fresh_pending_status(self, submit, refresh):
        submit.return_value = ({"success": True}, {})
        refresh.return_value = (
            {
                "verified_name": "Tanisha & Tushar's Hospitality Team",
                "name_status": "NON_EXISTS",
                "new_display_name": "Tanisha & Tushar's Hospitality Team",
                "new_name_status": "PENDING_REVIEW",
            },
            {},
        )

        response = self.client.post(
            self.url,
            {"action": "submit_display_name", "display_name": "Tanisha & Tushar's Hospitality Team"},
            format="json",
            HTTP_X_WEBHOOK_TOKEN="status-secret",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["display_name_status"]["new_name_status"], "PENDING_REVIEW")
        submit.assert_called_once_with(self.phone, "Tanisha & Tushar's Hospitality Team")

    @patch("MessageTemplates.whatsapp_views.waba_management.WEBHOOK_SECRET", "status-secret")
    @patch("MessageTemplates.whatsapp_views.waba_management.fetch_phone_display_name_status")
    @patch("MessageTemplates.whatsapp_views.waba_management.reregister_phone_number")
    def test_reregister_is_locked_before_new_name_approval(self, reregister, refresh):
        refresh.return_value = ({"new_name_status": "PENDING_REVIEW"}, {})

        response = self.client.post(
            self.url,
            {"action": "reregister", "pin": "123456"},
            format="json",
            HTTP_X_WEBHOOK_TOKEN="status-secret",
        )

        self.assertEqual(response.status_code, 409)
        reregister.assert_not_called()

    @patch("MessageTemplates.whatsapp_views.waba_management.WEBHOOK_SECRET", "status-secret")
    def test_display_name_mutation_requires_server_secret(self):
        response = self.client.post(
            self.url,
            {"action": "submit_display_name", "display_name": "Name"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    @patch("MessageTemplates.whatsapp_views.waba_management.WEBHOOK_SECRET", "status-secret")
    @patch("MessageTemplates.whatsapp_views.waba_management.submit_phone_display_name")
    def test_submit_cannot_change_the_synchronized_name(self, submit):
        response = self.client.post(
            self.url,
            {"action": "submit_display_name", "display_name": "A Different Name"},
            format="json",
            HTTP_X_WEBHOOK_TOKEN="status-secret",
        )

        self.assertEqual(response.status_code, 409)
        submit.assert_not_called()


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


class PhoneNumberOnboardingTests(APITestCase):
    @patch("MessageTemplates.serializers._fetch_meta_phone_numbers")
    def test_relinks_existing_display_number_to_meta_selected_identity(self, fetch_numbers):
        old_waba = WhatsAppBusinessAccount.objects.create(waba_id="old-waba", name="Old WABA")
        old_phone = WhatsAppPhoneNumber.objects.create(
            business_account=old_waba,
            phone_number_id="old-phone-id",
            asset_id="old-waba",
            waba_id="old-waba",
            display_phone_number="+91 96196 11453",
            normalized_display_phone_number="919619611453",
            verified_name="Old Event",
            is_active=False,
        )
        fetch_numbers.return_value = [
            {
                "id": "new-phone-id",
                "display_phone_number": "+91 96196 11453",
                "verified_name": "New Event",
                "quality_rating": "GREEN",
                "platform_type": "CLOUD_API",
            }
        ]

        serializer = WhatsAppPhoneNumberWriteSerializer(
            data={
                "phone_number_id": "new-phone-id",
                "waba_id": "new-waba",
                "asset_id": "new-waba",
                "access_token": "valid-meta-token",
                "display_phone_number": "+91 96196 11453",
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        phone = serializer.save()

        old_phone.refresh_from_db()
        self.assertEqual(phone.pk, old_phone.pk)
        self.assertEqual(phone.phone_number_id, "new-phone-id")
        self.assertEqual(phone.waba_id, "new-waba")
        self.assertEqual(phone.verified_name, "New Event")
        self.assertTrue(phone.is_active)
        self.assertEqual(WhatsAppPhoneNumber.objects.count(), 1)


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
