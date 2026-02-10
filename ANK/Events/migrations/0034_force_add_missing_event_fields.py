from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('Events', '0033_add_logistics_status'),
    ]

    # This migration was originally intended to "force add" missing fields on Event.
    # However, those fields (`client_name` and `type`) are already present on the
    # model and in the database in this project, so attempting to add them again
    # causes "duplicate column name" errors on migrate.
    #
    # To keep the migration history consistent without breaking existing databases,
    # we turn this into a no-op. Applying this migration will simply advance the
    # migration state without changing the schema.
    operations = []
