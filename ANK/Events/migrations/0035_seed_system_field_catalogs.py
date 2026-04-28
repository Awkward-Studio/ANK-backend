from django.db import migrations


def seed_system_field_catalogs(apps, schema_editor):
    EventField = apps.get_model("Events", "EventField")
    SessionField = apps.get_model("Events", "SessionField")
    EventRegistrationField = apps.get_model("Events", "EventRegistrationField")
    GuestField = apps.get_model("Guest", "GuestField")
    AccommodationField = apps.get_model("Logistics", "AccommodationField")
    TravelDetailField = apps.get_model("Logistics", "TravelDetailField")

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

    guest_fields = [
        ("name", "Name"),
        ("email", "Email Address"),
        ("phone", "Phone"),
        ("address", "Address"),
        ("city", "City"),
        ("nationality", "Nationality"),
        ("photo_id", "Photo ID"),
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
        ("logistics_status", "Logistics Status"),
        ("initiated_on", "Initiated On"),
        ("responded_on", "Responded On"),
        ("additional_guest_count", "Additional Guest Count"),
        ("whatsapp_opt_in_status", "WhatsApp Opt-in Status"),
        ("whatsapp_opt_in_sent_at", "WhatsApp Opt-In Sent At"),
        ("whatsapp_opted_in_at", "WhatsApp Opted In At"),
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
        ("event_hotel", "Event Hotel"),
        ("sharing_with", "Sharing With"),
        ("event_room_type", "Room Type"),
    ]

    travel_detail_fields = [
        ("travel_type", "Travel Type"),
        ("arrival", "Arrival Mode"),
        ("arrival_date", "Arrival Date"),
        ("flight_number", "Arrival Flight Number"),
        ("airline", "Arrival Airline"),
        ("pnr", "Arrival PNR"),
        ("terminal", "Terminal"),
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

    for name, label in event_fields:
        EventField.objects.get_or_create(name=name, defaults={"label": label})

    for name, label in guest_fields:
        GuestField.objects.get_or_create(name=name, defaults={"label": label})

    for name, label in session_fields:
        SessionField.objects.get_or_create(name=name, defaults={"label": label})

    for name, label in event_registration_fields:
        EventRegistrationField.objects.get_or_create(name=name, defaults={"label": label})

    for name, label in accommodation_fields:
        AccommodationField.objects.get_or_create(name=name, defaults={"label": label})

    for name, label in travel_detail_fields:
        TravelDetailField.objects.get_or_create(name=name, defaults={"label": label})


class Migration(migrations.Migration):

    dependencies = [
        ("Events", "0034_force_add_missing_event_fields"),
        ("Guest", "0003_alter_guest_address_alter_guest_city_and_more"),
        ("Logistics", "0023_cleanup_field_entries"),
    ]

    operations = [
        migrations.RunPython(seed_system_field_catalogs, migrations.RunPython.noop),
    ]

