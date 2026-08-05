from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("Manpower", "0028_freelancer_first_name_freelancer_title_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="posteventadjustment",
            name="freelancer_digital_signature",
            field=models.CharField(blank=True, max_length=200),
        ),
    ]
