from django.db import migrations, models


def populate_normalized_display_phone_number(apps, schema_editor):
    WhatsAppPhoneNumber = apps.get_model("MessageTemplates", "WhatsAppPhoneNumber")
    for phone in WhatsAppPhoneNumber.objects.all().iterator():
        phone.normalized_display_phone_number = "".join(
            char for char in str(phone.display_phone_number or "") if char.isdigit()
        )
        phone.save(update_fields=["normalized_display_phone_number"])


class Migration(migrations.Migration):
    dependencies = [("MessageTemplates", "0012_whatsapp_hosted_reconciliation")]

    operations = [
        migrations.AddField(
            model_name="whatsappphonenumber",
            name="normalized_display_phone_number",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="Digits-only display number used to prevent duplicate onboarding",
                max_length=20,
            ),
        ),
        migrations.RunPython(populate_normalized_display_phone_number, migrations.RunPython.noop),
    ]
