from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("Staff", "0007_add_accounts_role_choice"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="role",
            field=models.CharField(
                choices=[
                    ("admin", "Admin"),
                    ("staff", "Staff"),
                    ("super_admin", "Super Admin"),
                    ("department_head", "Department Head"),
                    ("security", "Security"),
                ],
                max_length=20,
            ),
        ),
    ]
