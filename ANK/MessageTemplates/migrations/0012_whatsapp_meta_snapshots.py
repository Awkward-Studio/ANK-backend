from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("MessageTemplates", "0011_whatsappphonenumber_meta_status")]

    operations = [
        migrations.AddField(model_name="whatsappbusinessaccount", name="token_expires_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="whatsappbusinessaccount", name="data_access_expires_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="whatsappbusinessaccount", name="template_access_status", field=models.CharField(default="unknown", max_length=20)),
        migrations.AddField(model_name="whatsappbusinessaccount", name="template_access_reason", field=models.TextField(blank=True)),
        migrations.AddField(model_name="whatsappbusinessaccount", name="template_access_last_checked_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="whatsappbusinessaccount", name="meta_last_attempt_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="whatsappbusinessaccount", name="meta_last_success_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="whatsappbusinessaccount", name="meta_fetch_error_code", field=models.CharField(blank=True, max_length=100)),
        migrations.AddField(model_name="whatsappbusinessaccount", name="meta_fetch_error_message", field=models.TextField(blank=True)),
        migrations.AddField(
            model_name="whatsappphonenumber",
            name="meta_access_state",
            field=models.CharField(
                choices=[("never_checked", "Never checked"), ("reachable", "Reachable"), ("not_in_waba", "Not in WABA"), ("access_denied", "Access denied"), ("token_expired", "Token expired"), ("partial", "Partial"), ("error", "Error")],
                db_index=True,
                default="never_checked",
                max_length=20,
            ),
        ),
        migrations.AddField(model_name="whatsappphonenumber", name="meta_seen_in_waba", field=models.BooleanField(blank=True, null=True)),
        migrations.AddField(model_name="whatsappphonenumber", name="meta_last_attempt_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="whatsappphonenumber", name="meta_last_success_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="whatsappphonenumber", name="meta_fetch_error_code", field=models.CharField(blank=True, max_length=100)),
        migrations.AddField(model_name="whatsappphonenumber", name="meta_fetch_error_message", field=models.TextField(blank=True)),
        migrations.AddField(model_name="whatsappphonenumber", name="meta_details_snapshot", field=models.JSONField(blank=True, default=dict)),
        migrations.AddField(model_name="whatsappphonenumber", name="code_verification_status", field=models.CharField(blank=True, max_length=50)),
        migrations.AddField(model_name="whatsappphonenumber", name="name_status", field=models.CharField(blank=True, max_length=50)),
        migrations.AddField(model_name="whatsappphonenumber", name="new_name_status", field=models.CharField(blank=True, max_length=50)),
        migrations.AddField(model_name="whatsappphonenumber", name="account_mode", field=models.CharField(blank=True, max_length=50)),
        migrations.AddField(model_name="whatsappphonenumber", name="is_official_business_account", field=models.BooleanField(blank=True, null=True)),
    ]
