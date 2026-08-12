from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("Manpower", "0031_freelancer_identity_documents"),
    ]

    operations = [
        migrations.AddField(
            model_name="manpowersettings",
            name="invoice_authorised_signatory_name",
            field=models.CharField(default="Divya Jain", max_length=200),
        ),
        migrations.AddField(
            model_name="manpowersettings",
            name="invoice_authorised_signatory_title",
            field=models.CharField(default="Manager People & Strategy", max_length=200),
        ),
    ]
