from django.db import migrations


def reconcile_event_columns(apps, schema_editor):
    Event = apps.get_model("Events", "Event")
    connection = schema_editor.connection
    table_name = Event._meta.db_table

    with connection.cursor() as cursor:
        table_names = set(connection.introspection.table_names(cursor))
        if table_name not in table_names and table_name.lower() in table_names:
            table_name = table_name.lower()

        existing_cols = {
            column.name
            for column in connection.introspection.get_table_description(
                cursor, table_name
            )
        }

    quoted_table = schema_editor.quote_name(table_name)

    if "client_name" not in existing_cols:
        schema_editor.execute(
            f"ALTER TABLE {quoted_table} ADD COLUMN client_name varchar(200) NULL;"
        )

    if "type" not in existing_cols:
        schema_editor.execute(
            f"ALTER TABLE {quoted_table} ADD COLUMN type varchar(20) NOT NULL DEFAULT 'wedding';"
        )


class Migration(migrations.Migration):

    dependencies = [
        ("Events", "0037_alter_whatsappmessagelog_message_type"),
    ]

    operations = [
        migrations.RunPython(reconcile_event_columns, migrations.RunPython.noop),
    ]
