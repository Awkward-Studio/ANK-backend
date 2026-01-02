from django.db import migrations
import uuid

def populate_accommodation_fields(apps, schema_editor):
    AccommodationField = apps.get_model('Logistics', 'AccommodationField')
    
    fields = [
        # Existing fields (ensuring they exist)
        ("room_count", "Room Count"),
        ("bed_type", "Bed Type"),
        ("check_in", "Check In"),
        ("check_out", "Check Out"),
        ("rooming_remarks", "Rooming Remarks"),
        # Missing fields to be added
        ("event", "Event"),
        ("event_registrations", "Event Registrations"),
        ("extra_attendees", "Extra Attendees"),
        # Note: 'hotel' might be redundant if 'event_hotel' is used, but per request:
        ("hotel", "Hotel (General)"),
        ("event_hotel", "Event Hotel"),
        ("hotel_name", "Hotel Name"),
        ("hotel_city", "Hotel City"),
        ("sharing_with", "Sharing With"),
        ("room_type", "Room Type (Legacy)"),
        ("event_room_type", "Room Type"),
    ]

    for name, label in fields:
        if not AccommodationField.objects.filter(name=name).exists():
            AccommodationField.objects.create(
                id=uuid.uuid4(),
                name=name,
                label=label
            )

def reverse_populate(apps, schema_editor):
    # We generally don't delete data in reverse migrations unless strictly necessary
    # to avoid data loss if we roll back. But technically we could delete the ones we added.
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('Logistics', '0021_hotel_is_venue_hotel_venue_list_alter_hotel_address_and_more'),
    ]

    operations = [
        migrations.RunPython(populate_accommodation_fields, reverse_populate),
    ]
