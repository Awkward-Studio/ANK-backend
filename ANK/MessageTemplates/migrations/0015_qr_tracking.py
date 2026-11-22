import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
from django.utils import timezone


class Migration(migrations.Migration):
    dependencies = [
        ("Events", "0042_add_check_in_counts"),
        ("MessageTemplates", "0014_broadcastrecipient"),
    ]

    operations = [
        migrations.AddField(
            model_name="messagetemplate",
            name="is_qr_template",
            field=models.BooleanField(
                default=False,
                help_text="Generate a unique encrypted security QR image for each recipient.",
            ),
        ),
        migrations.CreateModel(
            name="QrTemplateConfig",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("phone_number_id", models.CharField(db_index=True, max_length=100)),
                ("template_name", models.CharField(max_length=255)),
                ("language", models.CharField(default="en_US", max_length=20)),
                ("is_qr_template", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(default=timezone.now, editable=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("phone_number_id", "template_name", "language"),
                        name="qr_template_config_unique",
                    )
                ]
            },
        ),
        migrations.CreateModel(
            name="QrTicket",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("template_name", models.CharField(db_index=True, max_length=255)),
                ("template_language", models.CharField(default="en_US", max_length=20)),
                ("sender_phone_number_id", models.CharField(db_index=True, max_length=100)),
                ("recipient_phone", models.CharField(db_index=True, max_length=50)),
                ("recipient_name", models.CharField(blank=True, max_length=255)),
                ("media_id", models.CharField(blank=True, max_length=255)),
                ("token_digest", models.CharField(max_length=64, unique=True)),
                ("message_wamid", models.CharField(blank=True, db_index=True, max_length=255)),
                ("generated_at", models.DateTimeField(default=timezone.now, editable=False)),
                ("last_scanned_at", models.DateTimeField(blank=True, null=True)),
                ("scan_count", models.PositiveIntegerField(default=0)),
                ("campaign", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="qr_tickets", to="MessageTemplates.broadcastcampaign")),
                ("campaign_recipient", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="qr_tickets", to="MessageTemplates.broadcastrecipient")),
                ("event", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="qr_tickets", to="Events.event")),
                ("event_registration", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="qr_tickets", to="Events.eventregistration")),
                ("session_registration", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="qr_tickets", to="Events.sessionregistration")),
            ],
            options={
                "indexes": [
                    models.Index(fields=["event", "template_name"], name="MessageTem_event_i_8a0eb0_idx"),
                    models.Index(fields=["event_registration", "generated_at"], name="MessageTem_event_r_8c4d2c_idx"),
                    models.Index(fields=["campaign_recipient", "generated_at"], name="MessageTem_campaig_2a5b7e_idx"),
                ]
            },
        ),
        migrations.CreateModel(
            name="QrScanEvent",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("token_digest", models.CharField(db_index=True, max_length=64)),
                ("action", models.CharField(choices=[("verified", "Verified"), ("checked_in", "Checked In"), ("duplicate", "Duplicate Check-in"), ("rejected", "Rejected")], max_length=20)),
                ("error_message", models.TextField(blank=True)),
                ("scanned_at", models.DateTimeField(default=timezone.now, db_index=True)),
                ("event", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="qr_scans", to="Events.event")),
                ("security_user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="qr_scan_events", to=settings.AUTH_USER_MODEL)),
                ("session_registration", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="qr_scans", to="Events.sessionregistration")),
                ("ticket", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="scans", to="MessageTemplates.qrticket")),
            ],
            options={"ordering": ["-scanned_at"]},
        ),
    ]
