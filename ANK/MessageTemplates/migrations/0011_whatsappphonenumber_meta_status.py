from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("MessageTemplates", "0010_remove_messagetemplate_desc_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="whatsappphonenumber",
            name="meta_status",
            field=models.CharField(
                choices=[
                    ("active", "Active"),
                    ("blocked", "Blocked"),
                    ("logged_out", "Logged Out"),
                    ("unknown", "Unknown"),
                ],
                db_index=True,
                default="unknown",
                help_text="Current status from Meta reconciliation",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="whatsappphonenumber",
            name="meta_status_reason",
            field=models.TextField(
                blank=True,
                help_text="Human-readable reason for the last Meta status",
            ),
        ),
        migrations.AddField(
            model_name="whatsappphonenumber",
            name="meta_last_checked_at",
            field=models.DateTimeField(
                blank=True,
                help_text="Last time this number was reconciled with Meta",
                null=True,
            ),
        ),
    ]
