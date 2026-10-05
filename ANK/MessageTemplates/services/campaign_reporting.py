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


REPORT_STATES = ("pending", "sending", "sent", "delivered", "read", "failed", "unknown", "not_recorded", "flow_started")


def campaign_summary_stats(campaigns):
    """Count statuses in SQL without loading names, bodies, parameters, or errors."""
    from django.db.models import Case, Count, F, OuterRef, Subquery, Value, When, CharField
    from django.db.models.functions import Coalesce
    from MessageTemplates.models import BroadcastRecipient

    campaigns = list(campaigns)
    summaries = {campaign.pk: {**dict.fromkeys(REPORT_STATES, 0), "accepted": 0, "total": 0} for campaign in campaigns}
    if not campaigns:
        return summaries
    ids = list(summaries)
    matched_log = WhatsAppMessageLog.objects.filter(
        wamid=OuterRef("wamid"), recipient_id=OuterRef("phone"),
        sender_phone_number_id=OuterRef("campaign__sender_phone_number_id"),
    ).order_by()
    recipients = BroadcastRecipient.objects.filter(campaign_id__in=ids).annotate(
        effective_status=Coalesce(Subquery(matched_log.values("status")[:1]), Case(
            When(status="sending", attempted_at__lt=timezone.now() - timedelta(seconds=90), then=Value("unknown")),
            default=F("status"), output_field=CharField(),
        )),
        has_wamid=Case(When(wamid="", then=Value(0)), default=Value(1)),
    ).order_by().values("campaign_id", "effective_status", "has_wamid").annotate(count=Count("id"))
    roster_ids = set()
    for group in recipients:
        roster_ids.add(group["campaign_id"])
        stats = summaries[group["campaign_id"]]
        state = group["effective_status"] if group["effective_status"] in REPORT_STATES else "unknown"
        stats[state] += group["count"]
        stats["total"] += group["count"]
        stats["accepted"] += group["count"] if group["has_wamid"] else 0
    legacy_ids = set(ids) - roster_ids
    if legacy_ids:
        logs = WhatsAppMessageLog.objects.filter(campaign_id__in=legacy_ids).annotate(
            has_wamid=Case(When(wamid="", then=Value(0)), default=Value(1)),
        ).order_by().values("campaign_id", "status", "has_wamid").annotate(count=Count("id"))
        for group in logs:
            stats = summaries[group["campaign_id"]]
            state = group["status"] if group["status"] in REPORT_STATES else "unknown"
            stats[state] += group["count"]
            stats["total"] += group["count"]
            stats["accepted"] += group["count"] if group["has_wamid"] else 0
    for campaign in campaigns:
        stats = summaries[campaign.pk]
        missing = max(0, campaign.total_recipients - stats["total"])
        stats["not_recorded"] += missing
        stats["total"] += missing
    return summaries
