import csv
import io
from datetime import timedelta
from unittest.mock import patch

from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase
from Staff.models import User
from MessageTemplates.models import BroadcastCampaign, BroadcastRecipient
from Events.models.whatsapp_message_log import WhatsAppMessageLog


@override_settings(DJANGO_RSVP_SECRET="test-webhook-secret")
class BroadcastTrackingTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="campaign-tests@example.com", password="password", role="admin")
        self.client.force_authenticate(self.user)
        self.campaign = BroadcastCampaign.objects.create(name="Test campaign", template_name="c02", sender_phone_number_id="sender-1", total_recipients=3)
        self.url = f"/api/whatsapp/campaigns/{self.campaign.id}/"
        self.roster = [{"id": f"r{i}", "name": f"Guest {i}", "phone": f"91900000000{i}"} for i in range(3)]

    def save_roster(self):
        response = self.client.post(self.url + "recipients/", {"recipients": self.roster}, format="json")
        self.assertEqual(response.status_code, 200, response.data)

    def attempt(self, client_id="r0", operation="begin", **extras):
        return self.client.post(self.url + "recipient-attempt/", {"client_id": client_id, "operation": operation, "phone": self.roster[int(client_id[-1])]["phone"], "sender_phone_number_id": "sender-1", **extras}, format="json")

    def test_creation_saves_roster_atomically_and_counts_pending(self):
        response = self.client.post("/api/whatsapp/campaigns/", {"name": "New", "sender_phone_number_id": "sender-1", "total_recipients": 999, "recipients": self.roster}, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["total_recipients"], 3)
        self.assertEqual(response.data["stats"]["pending"], 3)
        self.assertEqual(BroadcastRecipient.objects.filter(campaign_id=response.data["id"]).count(), 3)

    def test_roster_verification_is_idempotent_and_rejects_changes(self):
        self.save_roster()
        self.save_roster()
        self.assertEqual(self.campaign.recipients.count(), 3)
        response = self.client.post(self.url + "recipients/", {"recipients": self.roster[:1]}, format="json")
        self.assertEqual(response.status_code, 409)

    def test_rejection_has_no_fake_wamid_and_survives_reload(self):
        self.save_roster()
        self.assertEqual(self.attempt(parameters=["A long name"]).status_code, 200)
        response = self.attempt(operation="finish", status="failed", error_code="132005", error_message="Template too long", error_details={"stage": "meta_rejection", "meta": {"error": {"code": 132005}}})
        self.assertEqual(response.status_code, 200, response.data)
        detail = self.client.get(self.url).data
        row = next(row for row in detail["logs"] if row["client_id"] == "r0")
        self.assertEqual(row["error_code"], "132005")
        self.assertEqual(row["body_parameters"], ["A long name"])
        self.assertFalse(row["wamid"])
        self.assertEqual(detail["stats"]["failed"], 1)
        self.assertEqual(detail["stats"]["pending"], 2)
        self.assertEqual(detail["stats"]["accepted"], 0)
        self.assertEqual(WhatsAppMessageLog.objects.count(), 0)

    def test_webhook_result_wins_even_if_it_arrived_before_tracking(self):
        self.save_roster()
        self.attempt()
        self.attempt(operation="finish", status="sent", wamid="wamid.real")
        WhatsAppMessageLog.objects.create(wamid="wamid.real", recipient_id=self.roster[0]["phone"], sender_phone_number_id="sender-1", status="read", read_at=timezone.now())
        stats = self.client.get(self.url).data["stats"]
        self.assertEqual(stats["read"], 1)
        self.assertEqual(stats["sent"], 0)
        self.assertEqual(stats["accepted"], 1)
        self.assertEqual(stats["pending"], 2)

    def test_delivery_failure_includes_webhook_code_and_details(self):
        self.save_roster()
        self.attempt()
        self.attempt(operation="finish", status="sent", wamid="wamid.failed")
        WhatsAppMessageLog.objects.create(wamid="wamid.failed", recipient_id=self.roster[0]["phone"], sender_phone_number_id="sender-1", status="failed", error_code="131026", error_message="Undeliverable", error_details={"pricing": {"category": "utility"}})
        detail = self.client.get(self.url).data
        row = next(row for row in detail["logs"] if row["client_id"] == "r0")
        self.assertEqual(row["error_code"], "131026")
        self.assertEqual(detail["stats"]["accepted"], 1)
        self.assertEqual(detail["stats"]["failed"], 1)

    def test_unknown_outcome_blocks_duplicate_send(self):
        self.save_roster()
        self.attempt()
        self.attempt(operation="finish", status="unknown", error_message="Timeout; verify before resending")
        self.assertEqual(self.attempt().status_code, 409)
        self.assertEqual(self.client.get(self.url).data["stats"]["unknown"], 1)

    def test_stale_sending_is_unknown_not_failed(self):
        self.save_roster()
        self.attempt()
        self.campaign.recipients.filter(client_id="r0").update(attempted_at=timezone.now() - timedelta(minutes=2))
        stats = self.client.get(self.url).data["stats"]
        self.assertEqual(stats["unknown"], 1)
        self.assertEqual(stats["failed"], 0)

    def test_begin_requires_matching_sender_phone_and_saved_recipient(self):
        self.assertEqual(self.attempt().status_code, 409)
        self.save_roster()
        self.assertEqual(self.attempt(sender_phone_number_id="other").status_code, 400)
        self.assertEqual(self.attempt(phone="919999999999").status_code, 400)

    def test_trusted_server_can_write_but_anonymous_cannot(self):
        self.save_roster()
        self.client.force_authenticate(None)
        self.assertIn(self.attempt().status_code, (401, 403))
        self.client.credentials(HTTP_X_WEBHOOK_TOKEN="test-webhook-secret")
        self.assertEqual(self.attempt().status_code, 200)
        self.assertIn(self.client.get(self.url).status_code, (401, 403))

    def test_legacy_gaps_are_explicit_and_not_counted_as_failures(self):
        WhatsAppMessageLog.objects.create(campaign=self.campaign, wamid="legacy", recipient_id="919000000000", sender_phone_number_id="sender-1", status="read")
        detail = self.client.get(self.url).data
        self.assertEqual(len(detail["logs"]), 3)
        self.assertEqual(detail["stats"]["not_recorded"], 2)
        self.assertEqual(detail["stats"]["failed"], 0)
        placeholders = [row for row in detail["logs"] if row["status"] == "not_recorded"]
        self.assertTrue(all(not row["recipient_id"] and not row["wamid"] for row in placeholders))

    def test_csv_exports_full_roster_and_exact_failure_subset(self):
        self.roster = [{"id": f"r{i}", "name": 'Guest, "quoted"\nनाम' if i == 0 else "=HYPERLINK(test)", "phone": f"91900000{i:04d}"} for i in range(65)]
        self.save_roster()
        self.attempt(parameters=['Quoted "name"'])
        self.attempt(operation="finish", status="failed", error_code="132005", error_message='Reason, "quoted"\nsecond line')
        response = self.client.get(self.url + "export/?scope=all")
        rows = list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"))))
        self.assertEqual(len(rows), 65)
        failed = next(row for row in rows if row["Status"] == "failed")
        self.assertEqual(failed["Name"], self.roster[0]["name"])
        self.assertEqual(failed["Phone"], self.roster[0]["phone"])
        self.assertEqual(failed["Error reason"], 'Reason, "quoted"\nsecond line')
        self.assertEqual(failed["Error code"], "132005")
        self.assertFalse(failed["WhatsApp message ID"])
        self.assertTrue(next(row for row in rows if row["Status"] == "pending")["Name"].startswith("'="))
        response = self.client.get(self.url + "export/?scope=failed")
        self.assertEqual(len(list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"))))), 1)
        self.assertEqual(len(self.client.get(self.url).data["logs"]), 65)

    def test_csv_legacy_gaps_are_exported_without_inventing_errors(self):
        response = self.client.get(self.url + "export/?scope=all")
        rows = list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"))))
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(row["Status"] == "not_recorded" and not row["Phone"] and row["Meta accepted"] == "unknown" for row in rows))
        response = self.client.get(self.url + "export/?scope=failed")
        self.assertEqual(len(list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"))))), 0)

    @patch.dict("os.environ", {"DJANGO_RSVP_SECRET": "test-webhook-secret"})
    def test_track_send_repairs_missing_attempt_completion(self):
        self.save_roster()
        self.attempt()
        self.client.force_authenticate(None)
        response = self.client.post("/api/webhooks/track-send/", {
            "wa_id": self.roster[0]["phone"], "template_wamid": "wamid.recovered", "template_name": "c02",
            "sender_phone_number_id": "sender-1", "campaign_id": str(self.campaign.id), "campaign_recipient_id": "r0",
        }, format="json", HTTP_X_WEBHOOK_TOKEN="test-webhook-secret")
        self.assertEqual(response.status_code, 200, response.content)
        recipient = self.campaign.recipients.get(client_id="r0")
        self.assertEqual(recipient.wamid, "wamid.recovered")
        self.assertEqual(recipient.status, "sent")

    def test_flow_start_is_not_counted_as_meta_acceptance(self):
        self.save_roster()
        self.attempt()
        self.assertEqual(self.attempt(operation="finish", status="flow_started").status_code, 200)
        stats = self.client.get(self.url).data["stats"]
        self.assertEqual(stats["flow_started"], 1)
        self.assertEqual(stats["accepted"], 0)
        self.assertEqual(stats["sent"], 0)

    def test_duplicate_recipient_ids_roll_back_campaign_creation(self):
        before = BroadcastCampaign.objects.count()
        response = self.client.post("/api/whatsapp/campaigns/", {"name": "Invalid", "sender_phone_number_id": "sender-1", "recipients": [self.roster[0], self.roster[0]]}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(BroadcastCampaign.objects.count(), before)

    def test_original_33_recipient_gap_is_visible_in_counts_and_csv(self):
        self.campaign.total_recipients = 33
        self.campaign.save()
        for i in range(23):
            state = "delivered" if i < 21 else "read" if i == 21 else "failed"
            WhatsAppMessageLog.objects.create(campaign=self.campaign, wamid=f"legacy-{i}", recipient_id=f"91900000{i:04d}", sender_phone_number_id="sender-1", status=state, error_code="131026" if state == "failed" else None)
        detail = self.client.get(self.url).data
        self.assertEqual(detail["stats"]["delivered"], 21)
        self.assertEqual(detail["stats"]["read"], 1)
        self.assertEqual(detail["stats"]["failed"], 1)
        self.assertEqual(detail["stats"]["not_recorded"], 10)
        self.assertEqual(len(detail["logs"]), 33)
        csv_rows = list(csv.DictReader(io.StringIO(self.client.get(self.url + "export/").content.decode("utf-8-sig"))))
        self.assertEqual(len(csv_rows), 33)
