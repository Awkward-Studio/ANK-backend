from django.db import migrations, models


def backfill_check_in_counts(apps, schema_editor):
    Event = apps.get_model("Events", "Event")
    EventRegistration = apps.get_model("Events", "EventRegistration")
    Session = apps.get_model("Events", "Session")
    SessionRegistration = apps.get_model("Events", "SessionRegistration")

    for event in Event.objects.all().iterator():
        event.check_in_count = EventRegistration.objects.filter(event_id=event.id, is_checked_in=True).count()
        event.save(update_fields=["check_in_count"])
    for session in Session.objects.all().iterator():
        session.check_in_count = SessionRegistration.objects.filter(session_id=session.id, is_checked_in=True).count()
        session.save(update_fields=["check_in_count"])


class Migration(migrations.Migration):
    dependencies = [("Events", "0041_add_attendance_fields")]

    operations = [
        migrations.AddField(
            model_name="event",
            name="check_in_count",
            field=models.PositiveIntegerField(
                default=0,
                help_text="Number of unique guest event check-ins recorded by security.",
            ),
        ),
        migrations.AddField(
            model_name="session",
            name="check_in_count",
            field=models.PositiveIntegerField(
                default=0,
                help_text="Number of unique guest check-ins recorded for this function.",
            ),
        ),
        migrations.RunPython(backfill_check_in_counts, migrations.RunPython.noop),
    ]
