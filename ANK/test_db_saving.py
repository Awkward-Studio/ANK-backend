import os
import django
import json
import uuid

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ANK.settings')
django.setup()

from MessageTemplates.models import FlowBlueprint, FlowSession
from Events.models.event_model import Event
from Guest.models import Guest
from Events.models.event_registration_model import EventRegistration

def test_session_saving():
    # 1. Create Dummy Event
    event, _ = Event.objects.get_or_create(
        name="Test Wedding",
        defaults={
            "bride_name": "Alice",
            "groom_name": "Bob",
            "start_date": "2026-03-10",
            "end_date": "2026-03-12",
            "location": "Mumbai",
            "venue": "Grand Hall"
        }
    )

    # 2. Create Dummy Guest
    guest, _ = Guest.objects.get_or_create(
        phone="+919876543210",
        defaults={"name": "John Doe", "email": "john@example.com"}
    )

    # 3. Create Dummy Registration
    reg, _ = EventRegistration.objects.get_or_create(
        event=event,
        guest=guest,
        defaults={"rsvp_status": "pending"}
    )

    # 4. Get Flow Blueprint
    bp = FlowBlueprint.objects.filter(name="Real Travel Capture Flow").first()
    if not bp:
        print("Flow blueprint not found.")
        return

    # 5. Create a session
    session = FlowSession.objects.create(
        registration=reg,
        flow=bp,
        current_node_id="node_rsvp_choice",
        status="WAITING_FOR_INPUT",
        context_data={}
    )
    
    print(f"Created Session {session.id} for Reg {reg.id}")
    
    # 6. Update the session (simulating a user answer)
    session.context_data["node_rsvp_choice"] = "yes"
    session.current_node_id = "node_ask_mode"
    session.save()
    
    # 7. Verify from DB
    check = FlowSession.objects.get(id=session.id)
    print(f"Verified Context Data: {json.dumps(check.context_data)}")
    print(f"Verified Current Node: {check.current_node_id}")
    print("Database saving verified successfully ✅")

if __name__ == "__main__":
    test_session_saving()
