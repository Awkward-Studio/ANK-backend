import os
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ANK.settings')
django.setup()

from MessageTemplates.models import WhatsAppBusinessAccount, WhatsAppPhoneNumber
from Guest.models import Guest
from Events.models.event_registration_model import EventRegistration
from django.conf import settings

# 1. Update/Create Business Account
waba_id = "910991641872001"
system_token = os.getenv("WHATSAPP_SYSTEM_TOKEN", "")

waba, created = WhatsAppBusinessAccount.objects.update_or_create(
    waba_id=waba_id,
    defaults={
        "name": "ANK Main WABA",
        "is_active": True
    }
)

# Store the token (Note: Requires WHATSAPP_ENCRYPTION_KEY in settings)
try:
    if system_token:
        waba.set_token(system_token)
        waba.save()
        print(f"✅ WABA {waba_id} updated with token.")
    else:
        print("WHATSAPP_SYSTEM_TOKEN not set; skipping token storage.")
except Exception as e:
    print(f"⚠️ Could not encrypt token (check WHATSAPP_ENCRYPTION_KEY): {e}")

# 2. Add the Phone Numbers
phone_data = [
    {"name": "Shweana and Vikram", "id": "1020590777800328", "number": "+919769600638"},
    {"name": "Ananya & Mudit", "id": "149080968288848", "number": "+918591910540"},
    {"name": "Rhea and Arjun", "id": "243070572230822", "number": "+919819114737"},
    {"name": "Vinisha and Vedang", "id": "317550154772764", "number": "+919820850574"},
    {"name": "A New Knot", "id": "870641679456253", "number": "+919987469537"},
    {"name": "Aashreen & Shaurya", "id": "403963616127926", "number": "+919769600802"},
]

for p in phone_data:
    obj, created = WhatsAppPhoneNumber.objects.update_or_create(
        phone_number_id=p["id"],
        defaults={
            "business_account": waba,
            "display_phone_number": p["number"],
            "verified_name": p["name"],
            "is_active": True,
            "is_default": (p["id"] == "1020590777800328")
        }
    )
    print(f"✅ Phone Number {p['name']} ({p['id']}) linked.")

# 3. Update the Test Guest to YOUR number for testing
# Using the number from your earlier logs
user_test_phone = "919470302380"
guest = Guest.objects.first()
if guest:
    guest.phone = user_test_phone
    guest.save()
    print(f"✅ Test Guest '{guest.name}' updated to your phone: {user_test_phone}")

print("\n🚀 Local Environment Setup Complete!")
