import sys
import os
import django

sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ANK.settings')
django.setup()

from Guest.models import Guest
from Events.models.event_registration_model import EventRegistration

names = ["Shweena", "Vikrant"]
for name in names:
    print(f"--- Searching for {name} ---")
    guests = Guest.objects.filter(name__icontains=name)
    if not guests.exists():
        print(f"No Guest found with name containing {name}")
    for g in guests:
        print(f"Guest: {g.name}, Phone: {g.phone}, ID: {g.id}")
        regs = EventRegistration.objects.filter(guest=g)
        for r in regs:
            print(f"  Registration: ID {r.id}, Event: {r.event.name}, RSVP: {r.rsvp_status}, Responded: {r.responded_on}")

