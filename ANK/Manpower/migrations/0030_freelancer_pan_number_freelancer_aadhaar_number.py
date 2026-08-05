from django.db import migrations, models


def backfill_government_ids(apps, schema_editor):
    Freelancer = apps.get_model("Manpower", "Freelancer")
    for freelancer in Freelancer.objects.all():
        id_number = (freelancer.id_number or "").strip()
        if not id_number:
            continue
        if freelancer.id_type == "AADHAR":
            freelancer.aadhaar_number = freelancer.aadhaar_number or id_number
        else:
            freelancer.pan_number = freelancer.pan_number or id_number
        freelancer.save(update_fields=["pan_number", "aadhaar_number"])


class Migration(migrations.Migration):

    dependencies = [
        ("Manpower", "0029_posteventadjustment_freelancer_digital_signature"),
    ]

    operations = [
        migrations.AddField(
            model_name="freelancer",
            name="pan_number",
            field=models.CharField(blank=True, help_text="PAN Number", max_length=20),
        ),
        migrations.AddField(
            model_name="freelancer",
            name="aadhaar_number",
            field=models.CharField(blank=True, help_text="Aadhaar Number", max_length=20),
        ),
        migrations.RunPython(backfill_government_ids, migrations.RunPython.noop),
    ]
