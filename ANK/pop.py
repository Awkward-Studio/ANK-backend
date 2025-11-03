import requests

BASE_URL = "https://api.anewknot.com/api"
# If your API is public or has sessionless access, leave TOKEN blank
TOKEN = ""  # or "Token yourtoken" if you use DRF TokenAuth
HEADERS = {
    "Content-Type": "application/json",
}
if TOKEN:
    HEADERS["Authorization"] = TOKEN

FIELD_ENDPOINTS = {
    "GuestField": "guest-fields/",
    "EventField": "event-fields/",
    "SessionField": "session-fields/",
    "AccommodationField": "accommodation-fields/",
    "TravelDetailField": "traveldetail-fields/",
    "EventRegistrationField": "eventregistration-fields/",
}

FIELD_SETS = {
    "GuestField": [
        ("name", "Name"),
        ("email", "Email Address"),
        ("phone", "Phone"),
        ("address", "Address"),
        ("city", "City"),
        ("nationality", "Nationality"),
        ("photo_id", "Photo ID"),
    ],
    "EventField": [
        ("name", "Name"),
        ("location", "Location"),
        ("venue", "Venue"),
        ("start_date", "Start Date"),
        ("end_date", "End Date"),
        ("pax", "Expected Pax"),
        ("bride_name", "Bride Name"),
        ("groom_name", "Groom Name"),
    ],
    "SessionField": [
        ("title", "Title"),
        ("description", "Description"),
        ("start_time", "Start Time"),
        ("end_time", "End Time"),
        ("pax", "Expected Pax"),
        ("date", "Date"),
        ("venue", "Venue"),
        ("location", "Location"),
    ],
    "EventRegistrationField": [
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
    ],
    "AccommodationField": [
        ("room_count", "Room Count"),
        ("bed_type", "Bed Type"),
        ("check_in", "Check In"),
        ("check_out", "Check Out"),
        ("rooming_remarks", "Rooming Remarks"),
    ],
    "TravelDetailField": [
        ("travel_type", "Travel Type"),
        ("arrival", "Arrival"),
        ("arrival_date", "Arrival Date"),
        ("flight_number", "Flight Number"),
        ("airline", "Airline"),
        ("pnr", "PNR"),
        ("arrival_time", "Arrival Time"),
        ("hotel_arrival_time", "Hotel Arrival Time"),
        ("departure_date", "Departure Date"),
        ("departure_time", "Departure Time"),
        ("departure_airline", "Departure Airline"),
        ("departure_pnr", "Departure PNR"),
    ],
}


def main():
    for model, endpoint in FIELD_ENDPOINTS.items():
        print(f"\n🚀 Populating {model} via {endpoint}")
        url = f"{BASE_URL}/{endpoint}"
        for name, label in FIELD_SETS[model]:
            data = {"name": name, "label": label}
            resp = requests.post(url, headers=HEADERS, json=data)
            if resp.status_code in [200, 201]:
                print(f"✅ Created {name}")
            elif resp.status_code == 400 and "unique" in resp.text.lower():
                print(f"⚪ Skipped {name} (already exists)")
            else:
                print(f"❌ Failed {name}: {resp.status_code} {resp.text}")


if __name__ == "__main__":
    main()
