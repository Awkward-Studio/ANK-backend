import csv
import hmac
import io
import json
import os

from django.conf import settings
from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination

from MessageTemplates.models import BroadcastCampaign, BroadcastRecipient
from MessageTemplates.serializers import BroadcastCampaignSerializer, BroadcastRecipientInputSerializer
from MessageTemplates.services.campaign_reporting import campaign_rows, campaign_stats


class CampaignAttemptPermission(BasePermission):
    def has_permission(self, request, view):
        secret = getattr(settings, "DJANGO_RSVP_SECRET", "") or os.getenv("DJANGO_RSVP_SECRET", "")
        token = request.headers.get("X-Webhook-Token", "")
        return bool(request.user and request.user.is_authenticated) or bool(secret and hmac.compare_digest(secret, token))


class AttemptInput(serializers.Serializer):
    client_id = serializers.CharField(max_length=255)
    operation = serializers.ChoiceField(choices=["begin", "finish"])
    status = serializers.ChoiceField(choices=["sent", "failed", "unknown", "flow_started"], required=False)
    wamid = serializers.CharField(max_length=255, allow_blank=True, required=False, default="")
    error_code = serializers.CharField(max_length=50, allow_blank=True, required=False, default="")
    error_message = serializers.CharField(allow_blank=True, required=False, default="")
    error_details = serializers.JSONField(required=False, default=dict)
    parameters = serializers.ListField(child=serializers.CharField(allow_blank=True), required=False, default=list)


class BroadcastCampaignViewSet(viewsets.ModelViewSet):
    queryset = BroadcastCampaign.objects.all().order_by("-created_at")
    permission_classes = [IsAuthenticated]
    serializer_class = BroadcastCampaignSerializer
    pagination_class = PageNumberPagination

    def get_queryset(self):
        qs = super().get_queryset()
        if self.action in ("list", "retrieve", "export"):
            qs = qs.prefetch_related("recipients", "logs")
        sender_id = self.request.query_params.get("sender_phone_number_id")
        return qs.filter(sender_phone_number_id=sender_id) if sender_id else qs

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        rows = campaign_rows(instance)
        data = self.get_serializer(instance).data
        data["stats"] = campaign_stats(rows)
        # Complete recipient roster, including pending and immediate rejections.
        data["logs"] = rows
        return Response(data)

    @action(detail=True, methods=["post"])
    def recipients(self, request, pk=None):
        serializer = BroadcastRecipientInputSerializer(data=request.data.get("recipients"), many=True)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        ids = [value["id"] for value in values]
        if not values or len(ids) != len(set(ids)):
            return Response({"error": "Recipients must have unique IDs and cannot be empty."}, status=400)
        with transaction.atomic():
            campaign = BroadcastCampaign.objects.select_for_update().get(pk=self.get_object().pk)
            selected_sender = request.data.get("sender_phone_number_id")
            if selected_sender and selected_sender != campaign.sender_phone_number_id:
                return Response({"error": "The selected sender differs from this broadcast. Use the original sender or create a new broadcast."}, status=409)
            existing = list(campaign.recipients.all())
            incoming = {(value["id"], value["phone"].lstrip("+"), value["name"]) for value in values}
            if existing:
                saved = {(value.client_id, value.phone, value.name) for value in existing}
                if saved != incoming:
                    return Response({"error": "The saved recipient list cannot be changed. Create a new broadcast."}, status=409)
            else:
                if campaign.logs.exists():
                    return Response({"error": "Cannot replace historical recipients. Create a new broadcast."}, status=409)
                BroadcastRecipient.objects.bulk_create([
                    BroadcastRecipient(campaign=campaign, client_id=value["id"], phone=value["phone"].lstrip("+"), name=value["name"])
                    for value in values
                ])
                campaign.total_recipients = len(values)
                campaign.save(update_fields=["total_recipients"])
        return Response({"ok": True, "count": len(values)})

    @action(detail=True, methods=["post"], url_path="recipient-attempt", permission_classes=[CampaignAttemptPermission], throttle_classes=[])
    def recipient_attempt(self, request, pk=None):
        serializer = AttemptInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        value = serializer.validated_data
        with transaction.atomic():
            campaign = BroadcastCampaign.objects.select_for_update().get(pk=self.get_object().pk)
            recipient = campaign.recipients.select_for_update().filter(client_id=value["client_id"]).first()
            if not recipient:
                return Response({"error": "Save the complete recipient list before sending."}, status=409)
            if value["operation"] == "begin":
                if recipient.status != "pending":
                    return Response({"error": "This recipient has already been attempted. Verify the recorded result before resending.", "recipient_status": recipient.status, "wamid": recipient.wamid}, status=409)
                if request.data.get("phone") != recipient.phone or request.data.get("sender_phone_number_id") != campaign.sender_phone_number_id:
                    return Response({"error": "Recipient or sender does not match this campaign."}, status=400)
                recipient.status = "sending"
                recipient.attempted_at = timezone.now()
                recipient.parameters = value["parameters"]
            else:
                if "status" not in value:
                    return Response({"error": "A send result requires a status."}, status=400)
                # A repeated completion can be acknowledged, but cannot overwrite it.
                if recipient.status != "sending":
                    if recipient.status == value["status"] and recipient.wamid == value["wamid"]:
                        return Response({"ok": True})
                    return Response({"error": "The send result has already been recorded or the send was never started."}, status=409)
                recipient.status = value["status"]
                recipient.wamid = value["wamid"]
                recipient.error_code = value["error_code"]
                recipient.error_message = value["error_message"]
                recipient.error_details = value["error_details"]
                if recipient.status == "sent":
                    recipient.sent_at = timezone.now()
                elif recipient.status == "failed":
                    recipient.failed_at = timezone.now()
            recipient.save()
            if not campaign.recipients.filter(status__in=["pending", "sending"]).exists():
                campaign.status = "completed"
                campaign.save(update_fields=["status"])
        return Response({"ok": True})

    @action(detail=True, methods=["get"], url_path="export")
    def export(self, request, pk=None):
        scope = request.query_params.get("scope", "all")
        if scope not in ("all", "failed"):
            return Response({"error": "scope must be all or failed"}, status=400)
        campaign = self.get_object()
        rows = campaign_rows(campaign)
        if scope == "failed":
            rows = [row for row in rows if row["status"] == "failed"]
        output = io.StringIO(newline="")
        writer = csv.writer(output, quoting=csv.QUOTE_ALL)
        writer.writerow(["Campaign ID", "Campaign", "Template", "Sender ID", "Recipient ID", "Phone", "Name", "Status", "Outcome source", "Meta accepted", "Error code", "Error reason", "WhatsApp message ID", "Attempted at", "Accepted at", "Delivered at", "Read at", "Failed at", "Body parameters", "Error details"])
        def safe(value):
            text = "" if value is None else str(value)
            # Prevent spreadsheet formula execution in user-controlled cells.
            if text.lstrip().startswith(("=", "+", "-", "@")) or text.startswith(("\t", "\r", "\n")):
                return "'" + text
            return text
        for row in rows:
            writer.writerow([safe(value) for value in (
                campaign.id, campaign.name, campaign.template_name, campaign.sender_phone_number_id,
                row["id"], row["recipient_id"], row.get("guest_name"), row["status"], row.get("outcome_source", "message_tracking"),
                "yes" if row.get("wamid") else "no" if row["status"] in ("pending", "failed") else "unknown", row.get("error_code"), row.get("error_message"), row.get("wamid"),
                row.get("attempted_at"), row.get("sent_at"), row.get("delivered_at"), row.get("read_at"), row.get("failed_at"),
                json.dumps(row.get("body_parameters", []), ensure_ascii=False), json.dumps(row.get("error_details", {}), ensure_ascii=False),
            )])
        response = HttpResponse("\ufeff" + output.getvalue(), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="campaign_{campaign.id}_{scope}.csv"'
        response["Cache-Control"] = "no-store"
        return response
