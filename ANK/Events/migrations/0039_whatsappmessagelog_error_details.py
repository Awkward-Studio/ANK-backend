from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("Events", "0038_reconcile_event_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="whatsappmessagelog",
            name="error_details",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
