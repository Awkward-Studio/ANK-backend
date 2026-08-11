from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("Manpower", "0030_freelancer_pan_number_freelancer_aadhaar_number"),
    ]

    operations = [
        migrations.AddField(
            model_name="freelancer",
            name="aadhaar_document",
            field=models.FileField(
                blank=True,
                null=True,
                upload_to="freelancer_documents/aadhaar/",
            ),
        ),
        migrations.AddField(
            model_name="freelancer",
            name="pan_document",
            field=models.FileField(
                blank=True,
                null=True,
                upload_to="freelancer_documents/pan/",
            ),
        ),
    ]
