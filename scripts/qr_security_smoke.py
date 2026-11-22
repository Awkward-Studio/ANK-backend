"""Local QR-ticket -> security verify -> check-in smoke test.

This uses Django's test client and mocks only the Meta media upload, so it never
sends a WhatsApp message. Run from Backend/ after migrations are applied:

    python scripts/qr_security_smoke.py
"""

import json
import os
import sys
from datetime import date
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ANK"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ANK.settings")
os.environ.setdefault("DJANGO_RSVP_SECRET", "local-qr-smoke-secret")

import django  # noqa: E402

django.setup()

from django.test import Client  # noqa: E402

from Events.models.event_model import Event  # noqa: E402
from Events.models.event_registration_model import EventRegistration  # noqa: E402
from Events.models.session_model import Session  # noqa: E402
from Events.models.session_registration import SessionRegistration  # noqa: E402
from Guest.models import Guest  # noqa: E402
from MessageTemplates.models import QrScanEvent, QrTemplateConfig, QrTicket  # noqa: E402


def main() -> int:
    client = Client()
    headers = {"HTTP_X_WEBHOOK_TOKEN": os.environ["DJANGO_RSVP_SECRET"]}
    guest = event = session = event_registration = session_registration = None
    config = None
    try:
        guest = Guest.objects.create(name="Local QR Smoke Guest", phone="919900001111")
        event = Event.objects.create(name="Local QR Smoke Event", start_date=date.today())
        session = Session.objects.create(event=event, title="Local Smoke Function", date=date.today())
        event_registration = EventRegistration.objects.create(
            guest=guest, event=event, uid="LOCAL-QR-SMOKE", rsvp_status="yes"
        )
        session_registration = SessionRegistration.objects.create(guest=guest, session=session)
        config = QrTemplateConfig.objects.create(
            phone_number_id="local-sender",
            template_name="local_qr_smoke",
            language="en_US",
            is_qr_template=True,
        )

        issue_payload = {
            "recipient_name": guest.name,
            "recipient_phone": guest.phone,
            "sender_phone_number_id": "local-sender",
            "template_name": "local_qr_smoke",
            "template_language": "en_US",
            "registration_id": str(event_registration.id),
            "event_id": str(event.id),
            "session_registration_id": str(session_registration.id),
            "session_id": str(session.id),
            "details": {"source": "local-smoke", "gate": "North"},
        }

        with patch(
            "MessageTemplates.temporary_tools.qr_test_media._get_credentials",
            return_value=("local-token", "local-sender"),
        ), patch(
            "MessageTemplates.temporary_tools.qr_test_media._upload_qr_to_meta",
            return_value="local-media-id",
        ):
            issued = client.post("/api/whatsapp/qr-test-media/", issue_payload, content_type="application/json", **headers)
        assert issued.status_code == 201, issued.content.decode()
        token = issued.json()["qr_token"]

        verified = client.post(
            "/api/events/security/verify-pass/",
            {"token": token},
            content_type="application/json",
            **headers,
        )
        assert verified.status_code == 200 and verified.json().get("valid") is True, verified.content.decode()

        checked_in = client.post(
            "/api/events/security/check-in/",
            {"token": token, "session_id": str(session.id)},
            content_type="application/json",
            **headers,
        )
        assert checked_in.status_code == 200 and checked_in.json().get("success") is True, checked_in.content.decode()

        duplicate = client.post(
            "/api/events/security/check-in/",
            {"token": token, "session_id": str(session.id)},
            content_type="application/json",
            **headers,
        )
        assert duplicate.status_code == 409, duplicate.content.decode()

        ticket = QrTicket.objects.get(id=issued.json()["ticket_id"])
        actions = list(QrScanEvent.objects.filter(ticket=ticket).values_list("action", flat=True))
        assert actions.count("verified") == 1
        assert actions.count("checked_in") == 1
        assert actions.count("duplicate") == 1
        event.refresh_from_db()
        session.refresh_from_db()
        assert event.check_in_count == 1 and session.check_in_count == 1

        print(json.dumps({
            "ok": True,
            "ticket_id": str(ticket.id),
            "scan_actions": actions,
            "event_check_in_count": event.check_in_count,
            "session_check_in_count": session.check_in_count,
        }, indent=2))
        return 0
    finally:
        if guest:
            guest.delete()
        if event:
            event.delete()
        if config:
            config.delete()


if __name__ == "__main__":
    raise SystemExit(main())
