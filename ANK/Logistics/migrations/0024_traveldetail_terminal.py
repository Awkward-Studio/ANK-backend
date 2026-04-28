from django.db import migrations, models


def seed_terminal_field(apps, schema_editor):
    TravelDetailField = apps.get_model("Logistics", "TravelDetailField")
    TravelDetailField.objects.get_or_create(
        name="terminal",
        defaults={"label": "Terminal"},
    )


def remove_terminal_field(apps, schema_editor):
    TravelDetailField = apps.get_model("Logistics", "TravelDetailField")
    TravelDetailField.objects.filter(name="terminal").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("Logistics", "0023_cleanup_field_entries"),
    ]

    operations = [
        migrations.AddField(
            model_name="traveldetail",
            name="terminal",
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.RunPython(seed_terminal_field, remove_terminal_field),
    ]
