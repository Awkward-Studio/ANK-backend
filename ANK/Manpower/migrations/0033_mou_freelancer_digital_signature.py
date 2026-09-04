from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("Manpower", "0032_manpowersettings_invoice_authorised_signatory"),
    ]

    operations = [
        migrations.AddField(
            model_name="mou",
            name="freelancer_digital_signature",
            field=models.TextField(blank=True),
        ),
    ]
