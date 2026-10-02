"""The same authoritative recipient snapshot drives history, counts, and CSV."""
from datetime import timedelta
from django.utils import timezone
from Events.serializers.whatsapp_message_log_serializer import WhatsAppMessageLogSerializer
from Events.models.whatsapp_message_log import WhatsAppMessageLog


def campaign_rows(campaign):
    if hasattr(campaign, "_report_rows"):
        return campaign._report_rows
    recipients = list(campaign.recipients.all())
    if recipients:
        wamids = [recipient.wamid for recipient in recipients if recipient.wamid]
        logs = {log.wamid: log for log in WhatsAppMessageLog.objects.filter(
            wamid__in=wamids, sender_phone_number_id=campaign.sender_phone_number_id,
        )}
        rows = []
        for recipient in recipients:
            row = {
                "id": str(recipient.id), "client_id": recipient.client_id,
                "recipient_id": recipient.phone, "guest_name": recipient.name,
                "status": recipient.status, "wamid": recipient.wamid,
                "outcome_source": recipient.error_details.get("stage", "send_result") if isinstance(recipient.error_details, dict) else "send_result",
                "error_code": recipient.error_code, "error_message": recipient.error_message,
                "error_details": recipient.error_details, "body_parameters": recipient.parameters,
                "attempted_at": recipient.attempted_at, "sent_at": recipient.sent_at,
                "failed_at": recipient.failed_at, "delivered_at": None, "read_at": None,
            }
            log = logs.get(recipient.wamid)
            if log and log.recipient_id == recipient.phone:
                row["outcome_source"] = "message_tracking"
                for field in ("status", "sent_at", "delivered_at", "read_at", "failed_at"):
                    row[field] = getattr(log, field)
                if log.error_message or log.error_code:
                    row.update(error_code=log.error_code, error_message=log.error_message,
                               error_details=log.error_details)
            elif recipient.status == "sending" and recipient.attempted_at and recipient.attempted_at < timezone.now() - timedelta(seconds=90):
                row["outcome_source"] = "interrupted_send"
                row.update(status="unknown", error_message="The send did not record a final result. Delivery is unknown; verify before resending.")
            rows.append(row)
    else:
        rows = list(WhatsAppMessageLogSerializer(campaign.logs.all().order_by("sent_at", "id"), many=True).data)
    # Older campaigns never saved these identities. Do not label them as failures.
    for index in range(max(0, campaign.total_recipients - len(rows))):
        rows.append({"id": f"not-recorded-{index + 1}", "recipient_id": "", "guest_name": "",
                     "outcome_source": "not_recorded", "status": "not_recorded", "wamid": "", "error_code": "",
                     "error_message": "Historical recipient details and send outcome were not recorded.",
                     "error_details": {}, "sent_at": None})
    campaign._report_rows = rows
    return rows


def campaign_stats(rows):
    stats = {state: 0 for state in ("pending", "sending", "sent", "delivered", "read", "failed", "unknown", "not_recorded", "flow_started")}
    for row in rows:
        state = row["status"] if row["status"] in stats else "unknown"
        stats[state] += 1
    stats["accepted"] = sum(bool(row.get("wamid")) for row in rows)
    stats["total"] = len(rows)
    return stats
