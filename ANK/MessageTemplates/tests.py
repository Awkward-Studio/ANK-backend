import tracemalloc
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import requests
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile, TemporaryUploadedFile
from django.urls import reverse
from django.test import SimpleTestCase, override_settings
from rest_framework.test import APITestCase

from MessageTemplates.models import WhatsAppBusinessAccount, WhatsAppPhoneNumber
from MessageTemplates.serializers import WhatsAppPhoneNumberSerializer, WhatsAppPhoneNumberWriteSerializer
from MessageTemplates.services.hosted_reconciliation import apply_comparison
from MessageTemplates.services.meta_reconciliation import (
    _subscription_audit,
    _token_audit,
    phone_identity_verification,
    reconcile_waba_phone_numbers,
)
from Staff.models import User
from MessageTemplates.whatsapp_views.media_upload import WhatsAppMediaUploadView, _upload_slot


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


class WhatsAppMediaUploadTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="media-uploader@example.com",
            password="password",
            role="admin",
        )
        self.url = reverse("whatsapp-media-upload")

    def test_upload_requires_authentication(self):
        document = SimpleUploadedFile("brief.pdf", b"pdf", content_type="application/pdf")

        response = self.client.post(self.url, {"file": document}, format="multipart")

        self.assertEqual(response.status_code, 401)

    @patch("MessageTemplates.whatsapp_views.media_upload.requests.get")
    @patch("MessageTemplates.whatsapp_views.media_upload.requests.post")
    @patch("MessageTemplates.whatsapp_views.media_upload._get_credentials")
    def test_large_document_is_forwarded_to_meta_in_one_request(
        self,
        get_credentials,
        meta_post,
        meta_get,
    ):
        get_credentials.return_value = ("secret-access-token", "phone-1")
        upload_response = MagicMock(status_code=200, content=b'{"id":"media-1"}')
        upload_response.json.return_value = {"id": "media-1"}
        meta_post.return_value = upload_response
        url_response = MagicMock(status_code=200)
        url_response.json.return_value = {"url": "https://meta.example/media-1"}
        meta_get.return_value = url_response
        self.client.force_authenticate(self.user)
        document = SimpleUploadedFile(
            "Event Brief 2026.pdf",
            b"x" * (15 * 1024 * 1024),
            content_type="application/pdf",
        )

        response = self.client.post(
            self.url,
            {"file": document, "phone_number_id": "phone-1"},
            format="multipart",
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["mediaId"], "media-1")
        self.assertEqual(response.data["mediaType"], "document")
        get_credentials.assert_called_once_with("phone-1")
        self.assertEqual(meta_post.call_count, 1)
        post_kwargs = meta_post.call_args.kwargs
        fields = post_kwargs["data"].body.fields
        self.assertEqual(fields["messaging_product"], "whatsapp")
        self.assertEqual(fields["file"][0], "Event_Brief_2026.pdf")
        self.assertEqual(fields["file"][2], "application/pdf")
        self.assertNotIn("files", post_kwargs)
        self.assertIn("multipart/form-data; boundary=", post_kwargs["headers"]["Content-Type"])
        self.assertNotIn("secret-access-token", str(response.data))

    @patch("MessageTemplates.whatsapp_views.media_upload._get_credentials")
    def test_unsupported_document_type_is_rejected_before_credential_lookup(self, get_credentials):
        self.client.force_authenticate(self.user)
        document = SimpleUploadedFile(
            "archive.zip",
            b"not-supported",
            content_type="application/zip",
        )

        response = self.client.post(self.url, {"file": document}, format="multipart")

        self.assertEqual(response.status_code, 400)
        self.assertIn("Unsupported file type", response.data["error"])
        get_credentials.assert_not_called()

    @patch.dict("os.environ", {"META_APP_ID": "app-1"}, clear=False)
    @patch("MessageTemplates.whatsapp_views.media_upload.requests.post")
    @patch("MessageTemplates.whatsapp_views.media_upload._get_credentials")
    def test_large_template_video_returns_header_handle_without_temp_session(
        self,
        get_credentials,
        meta_post,
    ):
        get_credentials.return_value = ("secret-access-token", "phone-1")
        session_response = MagicMock(status_code=200)
        session_response.json.return_value = {"id": "upload-session-1"}
        upload_response = MagicMock(status_code=200)
        upload_response.json.return_value = {"h": "template-header-handle"}
        meta_post.side_effect = [session_response, upload_response]
        self.client.force_authenticate(self.user)
        video = SimpleUploadedFile(
            "Wedding Film.mp4",
            b"v" * (15 * 1024 * 1024),
            content_type="video/mp4",
        )

        response = self.client.post(
            self.url,
            {
                "file": video,
                "phone_number_id": "phone-1",
                "upload_type": "template",
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["mediaId"], "template-header-handle")
        self.assertEqual(response.data["headerHandle"], "template-header-handle")
        self.assertEqual(response.data["mediaType"], "video")
        self.assertEqual(meta_post.call_count, 2)

        session_call, upload_call = meta_post.call_args_list
        self.assertEqual(session_call.kwargs["params"]["file_length"], 15 * 1024 * 1024)
        self.assertEqual(session_call.kwargs["params"]["file_type"], "video/mp4")
        self.assertEqual(session_call.kwargs["params"]["file_name"], "Wedding_Film.mp4")
        self.assertEqual(upload_call.kwargs["headers"]["file_offset"], "0")
        self.assertEqual(upload_call.kwargs["headers"]["Content-Length"], str(15 * 1024 * 1024))
        self.assertEqual(upload_call.kwargs["data"].len, 15 * 1024 * 1024)

    @patch("MessageTemplates.whatsapp_views.media_upload.requests.get")
    @patch("MessageTemplates.whatsapp_views.media_upload.requests.post")
    @patch("MessageTemplates.whatsapp_views.media_upload._get_credentials")
    def test_known_extension_recovers_generic_browser_content_type(
        self,
        get_credentials,
        meta_post,
        meta_get,
    ):
        get_credentials.return_value = ("secret-access-token", "phone-1")
        upload_response = MagicMock(status_code=200)
        upload_response.json.return_value = {"id": "media-2"}
        meta_post.return_value = upload_response
        meta_get.return_value = MagicMock(status_code=404)
        self.client.force_authenticate(self.user)
        document = SimpleUploadedFile(
            "supplier-list.docx",
            b"docx-data",
            content_type="application/octet-stream",
        )

        response = self.client.post(self.url, {"file": document}, format="multipart")

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["mediaType"], "document")
        self.assertEqual(
            meta_post.call_args.kwargs["data"].body.fields["file"][2],
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

    @patch("MessageTemplates.whatsapp_views.media_upload.requests.get")
    @patch("MessageTemplates.whatsapp_views.media_upload.requests.post")
    @patch("MessageTemplates.whatsapp_views.media_upload._get_credentials")
    def test_transient_meta_failure_is_retried_once(
        self,
        get_credentials,
        meta_post,
        meta_get,
    ):
        get_credentials.return_value = ("secret-access-token", "phone-1")
        unavailable_response = MagicMock(status_code=503)
        successful_response = MagicMock(status_code=200)
        successful_response.json.return_value = {"id": "media-after-retry"}
        meta_post.side_effect = [unavailable_response, successful_response]
        meta_get.return_value = MagicMock(status_code=404)
        self.client.force_authenticate(self.user)
        document = SimpleUploadedFile("brief.pdf", b"pdf-data", content_type="application/pdf")

        response = self.client.post(self.url, {"file": document}, format="multipart")

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["mediaId"], "media-after-retry")
        self.assertEqual(meta_post.call_count, 2)


@override_settings(WHATSAPP_MEDIA_MAX_CONCURRENT_UPLOADS=1)
class WhatsAppMediaStreamingTests(SimpleTestCase):
    def test_daphne_leaves_multipart_parsing_to_django(self):
        from ANK.daphne_uploads import configure_daphne_uploads
        from daphne import http_protocol

        configure_daphne_uploads()
        configured_class = http_protocol.WebRequest
        configure_daphne_uploads()
        self.assertIs(http_protocol.WebRequest, configured_class)
        request = configured_class(MagicMock())
        request.content = BytesIO(b"multipart body handled by Django")
        request.requestHeaders.addRawHeader(b"Content-Type", b"multipart/form-data; boundary=test")
        with (
            patch.object(request, "process") as process,
            patch("twisted.web.http._getMultiPartArgs") as parse,
        ):
            request.requestReceived(b"POST", b"/api/whatsapp/media-upload/", b"HTTP/1.1")
        parse.assert_not_called()
        process.assert_called_once()
        self.assertFalse(request._parsePOSTFormSubmission)

    def upload(self, size, meta_post):
        document = TemporaryUploadedFile("Large Brief.pdf", "application/pdf", size, None)
        # A sparse temporary file exercises real disk reads without allocating
        # the entire fixture in memory.
        document.file.truncate(size)
        request = SimpleNamespace(FILES={"file": document}, data={"phone_number_id": "phone-1"})
        try:
            with (
                patch("MessageTemplates.whatsapp_views.media_upload._get_credentials", return_value=("test-token", "phone-1")),
                patch("MessageTemplates.whatsapp_views.media_upload.requests.post", side_effect=meta_post),
                patch("MessageTemplates.whatsapp_views.media_upload.requests.get", return_value=MagicMock(status_code=404)),
            ):
                return WhatsAppMediaUploadView().post(request)
        finally:
            document.close()

    def test_documents_up_to_100_mb_stream_with_bounded_memory(self):
        for size in (26 * 1024 * 1024, 50 * 1024 * 1024, 96 * 1024 * 1024, 100 * 1024 * 1024):
            with self.subTest(document_bytes=size):
                observed = {}

                def meta_post(url, **kwargs):
                    # Prepare through Requests too. Its normal files= path used
                    # to allocate more than twice the document size here.
                    request_kwargs = {k: v for k, v in kwargs.items() if k != "timeout"}
                    prepared = requests.Request("POST", url, **request_kwargs).prepare()
                    self.assertIs(prepared.body, kwargs["data"])
                    self.assertNotIn("Transfer-Encoding", prepared.headers)
                    expected_length = int(prepared.headers["Content-Length"])
                    count = 0
                    first = prepared.body.read(64 * 1024)
                    self.assertIn(b'name="messaging_product"', first)
                    self.assertIn(b'filename="Large_Brief.pdf"', first)
                    self.assertIn(b"Content-Type: application/pdf", first)
                    count += len(first)
                    while chunk := prepared.body.read(64 * 1024):
                        self.assertLessEqual(len(chunk), 64 * 1024)
                        count += len(chunk)
                    self.assertEqual(count, expected_length)
                    self.assertGreater(count, size)
                    observed["bytes"] = count
                    response = MagicMock(status_code=200)
                    response.json.return_value = {"id": f"media-{size}"}
                    return response

                tracemalloc.start()
                try:
                    response = self.upload(size, meta_post)
                    _, peak = tracemalloc.get_traced_memory()
                finally:
                    tracemalloc.stop()
                self.assertEqual(response.status_code, 200, response.data)
                self.assertEqual(response.data["mediaId"], f"media-{size}")
                self.assertIn("bytes", observed)
                self.assertLess(peak, 4 * 1024 * 1024)

    def test_above_100_mb_is_rejected_without_calling_meta(self):
        meta_post = MagicMock()
        response = self.upload(100 * 1024 * 1024 + 1, meta_post)
        self.assertEqual(response.status_code, 400)
        meta_post.assert_not_called()

    def test_meta_size_rejection_is_a_validation_error_without_retry(self):
        meta_post = MagicMock(return_value=MagicMock(status_code=413))
        response = self.upload(100 * 1024 * 1024, meta_post)
        self.assertEqual(response.status_code, 400)
        self.assertIn("choose a smaller file", response.data["error"])
        meta_post.assert_called_once()

    def test_retry_rebuilds_consumed_multipart_body(self):
        attempts = []

        def meta_post(url, **kwargs):
            body = kwargs["data"]
            count = 0
            while chunk := body.read(64 * 1024):
                count += len(chunk)
            attempts.append((body, count))
            response = MagicMock(status_code=503 if len(attempts) == 1 else 200)
            response.json.return_value = {"id": "media-after-retry"}
            return response

        response = self.upload(26 * 1024 * 1024, meta_post)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(len(attempts), 2)
        self.assertIsNot(attempts[0][0], attempts[1][0])
        self.assertEqual(attempts[0][1], attempts[1][1])
        self.assertGreater(attempts[1][1], 26 * 1024 * 1024)

    def test_busy_upload_is_rejected_and_slot_is_reusable(self):
        with _upload_slot() as acquired:
            self.assertTrue(acquired)
            response = WhatsAppMediaUploadView().post(SimpleNamespace())
            self.assertEqual(response.status_code, 429)
            self.assertEqual(response["Retry-After"], "10")
        with _upload_slot() as acquired:
            self.assertTrue(acquired)

    def test_timeout_is_bounded_and_releases_upload_slot(self):
        calls = []

        def meta_post(url, **kwargs):
            calls.append(kwargs)
            raise requests.Timeout("upstream stalled")

        response = self.upload(26 * 1024 * 1024, meta_post)
        self.assertEqual(response.status_code, 502)
        self.assertEqual(len(calls), 2)
        with _upload_slot() as acquired:
            self.assertTrue(acquired)

    def test_expired_deadline_stops_reading_and_prevents_retry(self):
        calls = []
        clock = [1000]

        def meta_post(url, **kwargs):
            calls.append(kwargs)
            clock[0] += 300
            kwargs["data"].read(64 * 1024)

        with patch("MessageTemplates.whatsapp_views.media_upload.time.monotonic", side_effect=lambda: clock[0]):
            response = self.upload(26 * 1024 * 1024, meta_post)
        self.assertEqual(response.status_code, 502)
        self.assertEqual(len(calls), 1)


@patch.dict("os.environ", {"WABA_ACCESS_TOKEN": "template-system-token"}, clear=False)
@patch("MessageTemplates.whatsapp_views.template_management.WEBHOOK_SECRET", "template-secret")
class WhatsAppTemplateManagementTests(APITestCase):
    def setUp(self):
        self.waba = WhatsAppBusinessAccount.objects.create(
            waba_id="waba-templates",
            name="Template WABA",
        )
        self.phone = WhatsAppPhoneNumber.objects.create(
            business_account=self.waba,
            phone_number_id="phone-templates",
            asset_id="phone-templates",
            waba_id="waba-templates",
            display_phone_number="+919999999998",
            verified_name="Template sender",
            platform_type="CLOUD_API",
        )
        self.url = reverse("whatsapp-template-management")
        self.headers = {
            "HTTP_X_WEBHOOK_TOKEN": "template-secret",
            "HTTP_X_REQUEST_ID": "request-template-test",
        }

    @patch("MessageTemplates.whatsapp_views.template_management.requests.get")
    def test_template_list_retries_one_transient_meta_failure(self, meta_get):
        unavailable = MagicMock(status_code=503, ok=False, text="unavailable")
        unavailable.json.return_value = {"error": {"message": "Meta unavailable"}}
        success = MagicMock(status_code=200, ok=True)
        success.json.return_value = {"data": [{"id": "template-1", "name": "welcome"}]}
        meta_get.side_effect = [unavailable, success]

        response = self.client.get(
            self.url,
            {"phone_number_id": self.phone.phone_number_id},
            **self.headers,
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["templates"][0]["name"], "welcome")
        self.assertEqual(response.data["request_id"], "request-template-test")
        self.assertEqual(meta_get.call_count, 2)

    @patch("MessageTemplates.whatsapp_views.template_management.requests.get")
    def test_template_list_returns_structured_retryable_transport_error(self, meta_get):
        meta_get.side_effect = requests.Timeout("Meta read timed out")

        response = self.client.get(
            self.url,
            {"phone_number_id": self.phone.phone_number_id},
            **self.headers,
        )

        self.assertEqual(response.status_code, 503, response.data)
        self.assertEqual(response.data["code"], "META_UNREACHABLE")
        self.assertTrue(response.data["retryable"])
        self.assertEqual(response.data["request_id"], "request-template-test")
        self.assertEqual(meta_get.call_count, 2)

    @patch("MessageTemplates.whatsapp_views.template_management.requests.post")
    def test_create_rejects_media_header_without_verified_handle(self, meta_post):
        response = self.client.post(
            self.url,
            {
                "phone_number_id": self.phone.phone_number_id,
                "name": "missing_media",
                "category": "UTILITY",
                "language": "en_US",
                "components": [
                    {"type": "HEADER", "format": "DOCUMENT"},
                    {"type": "BODY", "text": "Your document is ready."},
                ],
            },
            format="json",
            **self.headers,
        )

        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn("verified document header upload", response.data["error"])
        meta_post.assert_not_called()

    @patch("MessageTemplates.whatsapp_views.template_management.requests.post")
    def test_create_does_not_repeat_ambiguous_mutation(self, meta_post):
        unavailable = MagicMock(status_code=503, ok=False, text="unavailable")
        unavailable.json.return_value = {"error": {"message": "Meta unavailable"}}
        meta_post.return_value = unavailable

        response = self.client.post(
            self.url,
            {
                "phone_number_id": self.phone.phone_number_id,
                "name": "safe_create",
                "category": "UTILITY",
                "language": "en_US",
                "components": [{"type": "BODY", "text": "Your update is ready."}],
            },
            format="json",
            **self.headers,
        )

        self.assertEqual(response.status_code, 503, response.data)
        self.assertTrue(response.data["retryable"])
        self.assertEqual(meta_post.call_count, 1)


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


class SenderReconciliationTests(APITestCase):
    def setUp(self):
        self.waba = WhatsAppBusinessAccount.objects.create(
            waba_id="waba-sender",
            name="Sender WABA",
        )
        self.phone = WhatsAppPhoneNumber.objects.create(
            business_account=self.waba,
            phone_number_id="phone-sender",
            asset_id="phone-sender",
            waba_id="waba-sender",
            display_phone_number="+919999999999",
            verified_name="Old sender name",
        )

    @patch("MessageTemplates.services.meta_reconciliation.build_waba_verification")
    @patch("MessageTemplates.services.meta_reconciliation._template_management_capability")
    @patch("MessageTemplates.services.meta_reconciliation._fetch_waba_phone_numbers")
    def test_live_sender_refresh_skips_status_page_audits(
        self,
        fetch_numbers,
        template_capability,
        build_verification,
    ):
        fetch_numbers.return_value = (
            [
                {
                    "id": "phone-sender",
                    "display_phone_number": "+918888888888",
                    "verified_name": "Current sender name",
                    "quality_rating": "GREEN",
                    "platform_type": "CLOUD_API",
                    "name_status": "APPROVED",
                }
            ],
            "",
            "",
        )

        reconcile_waba_phone_numbers(self.waba, audit_capabilities=False)

        fetch_numbers.assert_called_once_with(self.waba, include_coexistence=False)
        template_capability.assert_not_called()
        build_verification.assert_not_called()
        self.phone.refresh_from_db()
        self.assertEqual(self.phone.display_phone_number, "+918888888888")
        self.assertEqual(self.phone.verified_name, "Current sender name")
        self.assertEqual(self.phone.meta_status, "active")
        self.assertTrue(self.phone.is_usable)


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
