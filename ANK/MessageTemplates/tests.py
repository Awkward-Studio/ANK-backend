from unittest.mock import Mock, patch

from django.test import RequestFactory, TestCase, override_settings

from MessageTemplates.models import WhatsAppBusinessAccount, WhatsAppPhoneNumber
from MessageTemplates.permissions import IsWhatsAppAdminOrInternalService
from MessageTemplates.services.meta_graph import MetaGraphClient, MetaPermissionError
from MessageTemplates.services.meta_reconciliation import reconcile_waba_phone_numbers


class MetaGraphClientTests(TestCase):
    @override_settings(
        META_GRAPH_API_BASE_URL="https://graph.facebook.com",
        META_GRAPH_API_VERSION="v25.0",
    )
    def test_paginates_phone_numbers(self):
        first = Mock(ok=True)
        first.json.return_value = {
            "data": [{"id": "1"}],
            "paging": {"next": "https://graph.facebook.com/v25.0/next"},
        }
        second = Mock(ok=True)
        second.json.return_value = {"data": [{"id": "2"}]}
        session = Mock()
        session.request.side_effect = [first, second]

        client = MetaGraphClient("test-token", session=session)
        self.assertEqual([item["id"] for item in client.list_phone_numbers("waba")], ["1", "2"])
        self.assertEqual(session.request.call_count, 2)


class MetaReconciliationTests(TestCase):
    def setUp(self):
        self.waba = WhatsAppBusinessAccount.objects.create(waba_id="waba-1", name="Test")
        self.phone = WhatsAppPhoneNumber.objects.create(
            business_account=self.waba,
            phone_number_id="phone-1",
            asset_id="asset-1",
            waba_id="waba-1",
            display_phone_number="+910000000000",
            verified_name="Old",
        )

    @patch("MessageTemplates.services.meta_reconciliation._get_waba_token", return_value="token")
    @patch("MessageTemplates.services.meta_reconciliation.MetaGraphClient")
    def test_records_exact_meta_fields_without_derived_blocked_status(self, client_class, _token):
        client = client_class.return_value
        client.list_phone_numbers.return_value = [
            {"id": "phone-1", "display_phone_number": "+911111111111", "verified_name": "Meta Name", "quality_rating": "RED"}
        ]
        client.get_phone_number.return_value = {
            "id": "phone-1",
            "code_verification_status": "VERIFIED",
            "name_status": "APPROVED",
            "quality_rating": "RED",
        }
        client.list_templates.return_value = []

        reconcile_waba_phone_numbers(self.waba)
        self.phone.refresh_from_db()
        self.assertEqual(self.phone.meta_access_state, "reachable")
        self.assertEqual(self.phone.meta_status, "active")
        self.assertEqual(self.phone.code_verification_status, "VERIFIED")
        self.assertEqual(self.phone.name_status, "APPROVED")
        self.assertEqual(self.phone.quality_rating, "RED")

    @patch("MessageTemplates.services.meta_reconciliation._get_waba_token", return_value="token")
    @patch("MessageTemplates.services.meta_reconciliation.MetaGraphClient")
    def test_failed_refresh_preserves_last_snapshot(self, client_class, _token):
        self.phone.meta_details_snapshot = {"quality_rating": "GREEN"}
        self.phone.save(update_fields=["meta_details_snapshot"])
        client_class.return_value.list_phone_numbers.side_effect = MetaPermissionError(
            "Permission denied", code=200, status_code=403
        )

        reconcile_waba_phone_numbers(self.waba)
        self.phone.refresh_from_db()
        self.assertEqual(self.phone.meta_access_state, "access_denied")
        self.assertEqual(self.phone.meta_details_snapshot, {"quality_rating": "GREEN"})


class WhatsAppPermissionTests(TestCase):
    @override_settings(ANK_INTERNAL_API_SECRET="current", ANK_INTERNAL_API_SECRET_PREVIOUS="previous")
    def test_accepts_rotating_internal_secrets(self):
        permission = IsWhatsAppAdminOrInternalService()
        factory = RequestFactory()
        current = factory.get("/", HTTP_X_INTERNAL_SERVICE_TOKEN="current")
        previous = factory.get("/", HTTP_X_INTERNAL_SERVICE_TOKEN="previous")
        invalid = factory.get("/", HTTP_X_INTERNAL_SERVICE_TOKEN="invalid")
        self.assertTrue(permission.has_permission(current, None))
        self.assertTrue(permission.has_permission(previous, None))
        self.assertFalse(permission.has_permission(invalid, None))
