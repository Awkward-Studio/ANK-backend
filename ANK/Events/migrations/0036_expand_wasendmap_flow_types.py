from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("Events", "0035_seed_system_field_catalogs"),
    ]

    operations = [
        migrations.AlterField(
            model_name="wasendmap",
            name="flow_type",
            field=models.CharField(
                blank=True,
                choices=[
                    ("travel", "Travel Capture Flow"),
                    ("rsvp", "RSVP Reply"),
                    ("flow", "Visual Flow"),
                    ("standalone", "Standalone Message"),
                    ("custom", "Custom Message"),
                ],
                db_index=True,
                max_length=32,
                null=True,
            ),
        ),
    ]
