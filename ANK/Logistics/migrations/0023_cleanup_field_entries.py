from django.db import migrations


def cleanup_and_update_fields(apps, schema_editor):
    """
    1. Remove legacy AccommodationField entries that don't match model fields
    2. Ensure all TravelDetailField and AccommodationField entries are up to date
    """
    AccommodationField = apps.get_model('Logistics', 'AccommodationField')
    TravelDetailField = apps.get_model('Logistics', 'TravelDetailField')
    
    # --- Remove legacy AccommodationFields that don't exist in the model ---
    legacy_accommodation_fields = ['hotel', 'hotel_name', 'hotel_city', 'room_type']
    AccommodationField.objects.filter(name__in=legacy_accommodation_fields).delete()
    
    # --- Current valid AccommodationFields (matching model + serializer) ---
    accommodation_fields = [
        ("room_count", "Room Count"),
        ("bed_type", "Bed Type"),
        ("check_in", "Check In"),
        ("check_out", "Check Out"),
        ("rooming_remarks", "Rooming Remarks"),
        ("event", "Event"),
        ("event_registrations", "Event Registrations"),
        ("extra_attendees", "Extra Attendees"),
        ("event_hotel", "Event Hotel"),
        ("sharing_with", "Sharing With"),
        ("event_room_type", "Room Type"),
    ]
    
    # --- Current valid TravelDetailFields (matching model + serializer) ---
    travel_detail_fields = [
        ("travel_type", "Travel Type"),
        ("arrival", "Arrival Mode"),
        ("arrival_date", "Arrival Date"),
        ("flight_number", "Arrival Flight Number"),
        ("airline", "Arrival Airline"),
        ("pnr", "Arrival PNR"),
        ("arrival_time", "Arrival Time"),
        ("arrival_details", "Arrival Details"),
        ("hotel_arrival_time", "Hotel Arrival Time"),
        ("hotel_departure_time", "Hotel Departure Time"),
        ("return_travel", "Return Travel Required"),
        ("departure", "Departure Mode"),
        ("departure_date", "Departure Date"),
        ("source_departure_time", "Source Departure Time"),
        ("departure_time", "Departure Time"),
        ("departure_details", "Departure Details"),
        ("departure_flight_number", "Departure Flight Number"),
        ("departure_airline", "Departure Airline"),
        ("departure_pnr", "Departure PNR"),
    ]
    
    # --- Ensure all AccommodationFields exist ---
    for name, label in accommodation_fields:
        AccommodationField.objects.get_or_create(
            name=name, 
            defaults={'label': label}
        )
    
    # --- Ensure all TravelDetailFields exist ---
    for name, label in travel_detail_fields:
        TravelDetailField.objects.get_or_create(
            name=name, 
            defaults={'label': label}
        )


def reverse_cleanup(apps, schema_editor):
    """
    Reverse migration - add back legacy fields
    (mainly for rollback purposes)
    """
    AccommodationField = apps.get_model('Logistics', 'AccommodationField')
    
    legacy_fields = [
        ("hotel", "Hotel (General)"),
        ("hotel_name", "Hotel Name"),
        ("hotel_city", "Hotel City"),
        ("room_type", "Room Type (Legacy)"),
    ]
    
    for name, label in legacy_fields:
        AccommodationField.objects.get_or_create(
            name=name,
            defaults={'label': label}
        )


class Migration(migrations.Migration):

    dependencies = [
        ('Logistics', '0022_populate_accommodation_fields'),
    ]

    operations = [
        migrations.RunPython(cleanup_and_update_fields, reverse_cleanup),
    ]
