from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("Events", "0036_expand_wasendmap_flow_types"),
    ]

    operations = [
        migrations.AlterField(
            model_name="whatsappmessagelog",
            name="message_type",
            field=models.CharField(
                choices=[
                    ("rsvp", "RSVP"),
                    ("custom", "Custom"),
                    ("travel", "Travel"),
                    ("template", "Template"),
                    ("bulk", "Bulk"),
                    ("flow", "Flow"),
                    ("button", "Button"),
                    ("interactive", "Interactive"),
                ],
                default="rsvp",
                max_length=20,
            ),
        ),
    ]
