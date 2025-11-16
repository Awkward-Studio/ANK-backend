# Migration neutralized to avoid duplicate column errors in production.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("Events", "0013_alter_eventregistration_guest_group_and_more"),
    ]

    operations = [
        migrations.RunSQL(sql="SELECT 1;", reverse_sql="SELECT 1;"),
    ]
