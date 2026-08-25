import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("Events", "0039_whatsappmessagelog_error_details"),
    ]

    operations = [
        migrations.CreateModel(
            name="WhatsAppWebhookReceipt",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("event_key", models.CharField(db_index=True, max_length=512, unique=True)),
                ("wamid", models.CharField(blank=True, db_index=True, default="", max_length=255)),
                ("event_kind", models.CharField(blank=True, default="", max_length=32)),
                ("event_name", models.CharField(blank=True, default="", max_length=64)),
                ("source_app", models.CharField(blank=True, default="", max_length=64)),
                ("state", models.CharField(choices=[("processing", "Processing"), ("completed", "Completed"), ("failed", "Failed")], default="processing", max_length=16)),
                ("claim_token", models.UUIDField(blank=True, null=True)),
                ("lease_expires_at", models.DateTimeField(blank=True, null=True)),
                ("attempts", models.PositiveIntegerField(default=0)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("first_seen_at", models.DateTimeField(auto_now_add=True)),
                ("last_seen_at", models.DateTimeField(auto_now=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={"ordering": ["-last_seen_at"]},
        ),
    ]
