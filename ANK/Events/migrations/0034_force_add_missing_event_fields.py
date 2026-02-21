from django.db import migrations, models, connection

def add_missing_columns(apps, schema_editor):
    table_name = 'Events_event'
    
    # We use a raw cursor to check for columns because different DBs 
    # have different ways to check schema.
    with connection.cursor() as cursor:
        if connection.vendor == 'sqlite':
            cursor.execute(f"PRAGMA table_info({table_name})")
            existing_cols = [row[1] for row in cursor.fetchall()]
        else:
            # Postgres: check information_schema
            cursor.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name=%s",
                [table_name.lower()]
            )
            existing_cols = [row[0] for row in cursor.fetchall()]

    # Add client_name if missing
    if 'client_name' not in existing_cols:
        schema_editor.execute(f'ALTER TABLE "{table_name}" ADD COLUMN client_name varchar(200) NULL;')
    
    # Add type if missing
    if 'type' not in existing_cols:
        schema_editor.execute(f'ALTER TABLE "{table_name}" ADD COLUMN type varchar(20) NOT NULL DEFAULT "wedding";')

class Migration(migrations.Migration):

    dependencies = [
        ('Events', '0033_add_logistics_status'),
    ]

    operations = [
        migrations.RunPython(add_missing_columns),
    ]
