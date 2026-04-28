import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("Departments", "0005_seed_accounts_department"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("Events", "0038_reconcile_event_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="EventHeadAssignment",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("assigned_on", models.DateTimeField(auto_now_add=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "event",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="event_head_assignments",
                        to="Events.event",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="event_head_assignments",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["event_id", "user_id"],
                "unique_together": {("event", "user")},
                "indexes": [
                    models.Index(fields=["event", "user"], name="Department_event_i_20203e_idx"),
                    models.Index(fields=["user", "event"], name="Department_user_id_67a122_idx"),
                ],
            },
        ),
    ]
