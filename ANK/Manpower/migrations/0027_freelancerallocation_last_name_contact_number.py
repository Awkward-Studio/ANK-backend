from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("Manpower", "0026_reset_manpower_meal_rates_to_zero"),
    ]

    operations = [
        migrations.AddField(
            model_name="freelancerallocation",
            name="last_name",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name="freelancerallocation",
            name="contact_number",
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
    ]