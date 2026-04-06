from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("Events", "0033_add_logistics_status"),
    ]

    # Keep this migration permanently stable.
    # Event.client_name and Event.type are reconciled elsewhere in the history,
    # and any schema repair must happen in a new migration rather than by
    # changing the meaning of Events.0034 again.
    operations = []
