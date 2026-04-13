from django.db import migrations, models


def backfill_requirement_names(apps, schema_editor):
    ManpowerRequirement = apps.get_model("Manpower", "ManpowerRequirement")
    for requirement in ManpowerRequirement.objects.all():
        fallback_name = (requirement.skill_category or "").strip() or "Unnamed Requirement"
        requirement.name = fallback_name
        requirement.save(update_fields=["name"])


class Migration(migrations.Migration):

    dependencies = [
        ("Manpower", "0023_manpowerrequirement_location"),
    ]

    operations = [
        migrations.AddField(
            model_name="manpowerrequirement",
            name="name",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.RunPython(backfill_requirement_names, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="manpowerrequirement",
            name="name",
            field=models.CharField(max_length=200),
        ),
    ]
