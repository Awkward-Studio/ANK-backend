import os
import django
import sys

sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ANK.settings')
django.setup()

from Events.models.event_registration_model import EventRegistration
from Events.models.whatsapp_message_log import WhatsAppMessageLog

print("--- Recent Registrations ---")
regs = EventRegistration.objects.all().order_by('-updated_at')[:5]
for r in regs:
    print(f"ID: {r.id}, Guest: {r.guest.name}, Phone: {r.guest.phone}, RSVP: {r.rsvp_status}, Name on Msg: {r.name_on_message}")

print("\n--- Recent WhatsApp Logs ---")
logs = WhatsAppMessageLog.objects.all().order_by('-sent_at')[:5]
for l in logs:
    print(f"ID: {l.id}, Direction: {l.direction}, Recipient: {l.recipient_id}, Status: {l.status}, Body: {l.body[:30]}...")

