from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('Events', '0033_add_logistics_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='event',
            name='client_name',
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
        migrations.AddField(
            model_name='event',
            name='type',
            field=models.CharField(
                choices=[('wedding', 'Wedding'), ('corporate', 'Corporate'), ('social', 'Social')],
                default='wedding',
                help_text='Type of event: Wedding, Corporate, or Social',
                max_length=20,
            ),
        ),
    ]
