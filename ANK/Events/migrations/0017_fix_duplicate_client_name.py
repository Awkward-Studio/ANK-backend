from django.db import migrations, connection


def fix_client_name(apps, schema_editor):
    # Skip when SQLite (local dev)
    if connection.vendor == "sqlite":
        return

    # Only for Postgres
    schema_editor.execute(
        'ALTER TABLE "Events_event" ADD COLUMN IF NOT EXISTS client_name varchar(255);'
    )


class Migration(migrations.Migration):

    dependencies = [
        ("Events", "0016_merge_0015_event_location_type_0015_session_venue"),
    ]

    operations = [
        migrations.RunPython(fix_client_name),
    ]
