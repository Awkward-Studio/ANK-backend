from django.db import migrations
import uuid

def populate_all_system_fields(apps, schema_editor):
    AccommodationField = apps.get_model('Logistics', 'AccommodationField')
    TravelDetailField = apps.get_model('Logistics', 'TravelDetailField')
    # GuestField = apps.get_model('Guest', 'GuestField')  # Assuming GuestField is in Guest app
    # EventField = apps.get_model('Events', 'EventField')
    # SessionField = apps.get_model('Events', 'SessionField')
    # EventRegistrationField = apps.get_model('Events', 'EventRegistrationField')
    
    # Check if models exist in schema (robustness)
    try:
        GuestField = apps.get_model('Guest', 'GuestField')
    except LookupError:
        GuestField = None

    try:
        EventField = apps.get_model('Events', 'EventField')
    except LookupError:
        EventField = None

    try:
        SessionField = apps.get_model('Events', 'SessionField')
    except LookupError:
        SessionField = None

    try:
        EventRegistrationField = apps.get_model('Events', 'EventRegistrationField')
    except LookupError:
        EventRegistrationField = None

    # --- Field Definitions ---

    guest_fields = [
        ("name", "Name"),
        ("email", "Email Address"),
        ("phone", "Phone"),
        ("address", "Address"),
        ("city", "City"),
        ("nationality", "Nationality"),
        ("photo_id", "Photo ID"),
    ]

    event_fields = [
        ("name", "Name"),
        ("client_name", "Client Name"),
        ("type", "Event Type"),
        ("location_type", "Location Type"),
        ("location", "Location"),
        ("venue", "Venue"),
        ("start_date", "Start Date"),
        ("end_date", "End Date"),
        ("pax", "Expected Pax"),
        ("bride_name", "Bride Name"),
        ("groom_name", "Groom Name"),
    ]

    session_fields = [
        ("title", "Title"),
        ("description", "Description"),
        ("start_time", "Start Time"),
        ("end_time", "End Time"),
        ("pax", "Expected Pax"),
        ("date", "Date"),
        ("venue", "Venue"),
        ("venue_name", "Venue Name"),
        ("location", "Location"),
        ("entertainment", "Entertainment"),
    ]

    event_registration_fields = [
        ("uid", "UID"),
        ("guest_group", "Guest Group"),
        ("sub_guest_group", "Sub Guest Group"),
        ("name_on_message", "Name on Message"),
        ("family_salutation", "Family Salutation"),
        ("title", "Title"),
        ("estimated_pax", "Estimated Pax"),
        ("visa_oci", "Visa/OCI"),
        ("hamper_count", "Hamper Count"),
        ("rsvp_status", "RSVP Status"),
        ("initiated_on", "Initiated On"),
        ("responded_on", "Responded On"),
        ("additional_guest_count", "Additional Guest Count"),
        ("whatsapp_opt_in_status", "WhatsApp Opt-in Status"),
    ]

    accommodation_fields = [
        ("room_count", "Room Count"),
        ("bed_type", "Bed Type"),
        ("check_in", "Check In"),
        ("check_out", "Check Out"),
        ("rooming_remarks", "Rooming Remarks"),
        ("event", "Event"),
        ("event_registrations", "Event Registrations"),
        ("extra_attendees", "Extra Attendees"),
        ("hotel", "Hotel (General)"),
        ("event_hotel", "Event Hotel"),
        ("hotel_name", "Hotel Name"),
        ("hotel_city", "Hotel City"),
        ("sharing_with", "Sharing With"),
        ("room_type", "Room Type (Legacy)"),
        ("event_room_type", "Room Type"),
    ]

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

    # --- Execution ---

    if GuestField:
        for name, label in guest_fields:
            GuestField.objects.get_or_create(name=name, defaults={'id': uuid.uuid4(), 'label': label})
    
    if EventField:
        for name, label in event_fields:
            EventField.objects.get_or_create(name=name, defaults={'id': uuid.uuid4(), 'label': label})

    if SessionField:
        for name, label in session_fields:
            SessionField.objects.get_or_create(name=name, defaults={'id': uuid.uuid4(), 'label': label})

    if EventRegistrationField:
        for name, label in event_registration_fields:
            EventRegistrationField.objects.get_or_create(name=name, defaults={'id': uuid.uuid4(), 'label': label})
            
    if AccommodationField:
        for name, label in accommodation_fields:
            AccommodationField.objects.get_or_create(name=name, defaults={'id': uuid.uuid4(), 'label': label})

    if TravelDetailField:
        for name, label in travel_detail_fields:
            TravelDetailField.objects.get_or_create(name=name, defaults={'id': uuid.uuid4(), 'label': label})


class Migration(migrations.Migration):

    dependencies = [
        ('Logistics', '0021_hotel_is_venue_hotel_venue_list_alter_hotel_address_and_more'),
        # Determine if we need dependencies on other apps (Events, Guest)
        # Ideally, we should add them if they are in separate apps.
        # However, circular dependencies can be tricky.
        # Since we use apps.get_model inside the function, strict dependency is less critical for *data* migration 
        # but we need the tables to exist.
        # Assuming Logistics depends on Events and Guest already (via FKs), it should be fine.
        ('Events', '0001_initial'), # Ensure Events app is migrated (replace with latest known if possible, or just rely on implied deps)
        # Note: If 'Guest' app exists, assume it's created.
    ]

    operations = [
        migrations.RunPython(populate_all_system_fields, migrations.RunPython.noop),
    ]
