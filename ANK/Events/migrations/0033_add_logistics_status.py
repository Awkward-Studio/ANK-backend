# Generated manually for logistics_status field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Events', '0032_whatsappmessagelog_campaign'),
    ]

    operations = [
        migrations.AddField(
            model_name='eventregistration',
            name='logistics_status',
            field=models.CharField(
                choices=[
                    ('not_started', 'Not Started'),
                    ('in_flight', 'In Flight'),
                    ('landed', 'Landed'),
                    ('received', 'Received'),
                    ('arrived_hotel', 'Arrived Hotel'),
                    ('checked_in', 'Checked In'),
                ],
                default='not_started',
                max_length=20,
            ),
        ),
    ]
