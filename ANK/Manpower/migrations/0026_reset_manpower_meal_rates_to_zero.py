from decimal import Decimal

from django.db import migrations


def reset_meal_rates_to_zero(apps, schema_editor):
    ManpowerSettings = apps.get_model("Manpower", "ManpowerSettings")
    settings = ManpowerSettings.objects.first()
    if settings is None:
        ManpowerSettings.objects.create(
            default_breakfast_rate=Decimal("0.00"),
            default_lunch_rate=Decimal("0.00"),
            default_dinner_rate=Decimal("0.00"),
        )
        return

    settings.default_breakfast_rate = Decimal("0.00")
    settings.default_lunch_rate = Decimal("0.00")
    settings.default_dinner_rate = Decimal("0.00")
    settings.save(update_fields=[
        "default_breakfast_rate",
        "default_lunch_rate",
        "default_dinner_rate",
        "updated_at",
    ])


class Migration(migrations.Migration):

    dependencies = [
        ("Manpower", "0025_alter_freelancerallocation_unique_together"),
    ]

    operations = [
        migrations.RunPython(reset_meal_rates_to_zero, migrations.RunPython.noop),
    ]
