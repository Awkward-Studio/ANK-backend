import json
import os
from unittest.mock import patch

from django.test import TestCase

from Events.models.whatsapp_message_log import WhatsAppMessageLog


class MessageStatusWebhookTests(TestCase):
    token = "test-webhook-secret"
    wamid = "wamid.test-message"

    def post_status(self, status, errors=None):
        payload = {
            "wamid": self.wamid,
            "recipient_id": "+919999999999",
            "status": status,
            "timestamp": "2026-08-24T10:17:07Z",
            "errors": errors,
            "pricing": {"category": "utility", "type": "regular"},
            "status_payload": {"id": self.wamid, "status": status},
        }
        with patch.dict(os.environ, {"DJANGO_RSVP_SECRET": self.token}):
            return self.client.post(
                "/api/webhooks/message-status/",
                data=json.dumps(payload),
                content_type="application/json",
                HTTP_X_WEBHOOK_TOKEN=self.token,
            )

    def test_failure_preserves_complete_meta_error_and_is_terminal(self):
        WhatsAppMessageLog.objects.create(
            wamid=self.wamid,
            recipient_id="919999999999",
            status="sent",
        )
        errors = [{
            "code": 131049,
            "title": "Meta chose not to deliver",
            "message": "This message was not delivered.",
            "error_data": {"details": "Maintain healthy ecosystem engagement."},
        }]

        response = self.post_status("failed", errors)
        self.assertEqual(response.status_code, 200)

        log = WhatsAppMessageLog.objects.get(wamid=self.wamid)
        self.assertEqual(log.status, "failed")
        self.assertEqual(log.error_code, "131049")
        self.assertIn("Meta chose not to deliver", log.error_message)
        self.assertIn("Maintain healthy ecosystem engagement", log.error_message)
        self.assertEqual(log.error_details["errors"], errors)
        self.assertEqual(log.error_details["pricing"]["category"], "utility")
        self.assertIsNotNone(log.failed_at)

        # A delayed tracking write must enrich the row without resetting the
        # already-recorded failure back to "sent".
        with patch.dict(os.environ, {"DJANGO_RSVP_SECRET": self.token}):
            tracking_response = self.client.post(
                "/api/webhooks/track-send/",
                data=json.dumps({
                    "wa_id": "+919999999999",
                    "template_wamid": self.wamid,
                    "template_name": "test_template",
                    "message_type": "template",
                }),
                content_type="application/json",
                HTTP_X_WEBHOOK_TOKEN=self.token,
            )
        self.assertEqual(tracking_response.status_code, 200)
        log.refresh_from_db()
        self.assertEqual(log.status, "failed")

        self.post_status("sent")
        log.refresh_from_db()
        self.assertEqual(log.status, "failed")

    def test_lookup_returns_code_details_and_unknown_ids(self):
        errors = [{"code": 131049, "title": "Meta chose not to deliver"}]
        self.post_status("failed", errors)

        with patch.dict(os.environ, {"DJANGO_RSVP_SECRET": self.token}):
            response = self.client.post(
                "/api/webhooks/message-status-lookup/",
                data=json.dumps({"wamids": [self.wamid, "wamid.missing"]}),
                content_type="application/json",
                HTTP_X_WEBHOOK_TOKEN=self.token,
            )

        self.assertEqual(response.status_code, 200)
        statuses = response.json()["statuses"]
        self.assertEqual(statuses[self.wamid]["error_code"], "131049")
        self.assertEqual(statuses[self.wamid]["error_details"]["errors"], errors)
        self.assertEqual(statuses[self.wamid]["error_details"]["pricing"]["category"], "utility")
        self.assertEqual(statuses["wamid.missing"]["status"], "unknown")
        self.assertEqual(statuses["wamid.missing"]["error_code"], "STATUS_NOT_TRACKED")
