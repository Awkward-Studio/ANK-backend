import os
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ANK.settings')
django.setup()

from MessageTemplates.models import WhatsAppBusinessAccount, WhatsAppPhoneNumber
from django.conf import settings

# Real Data from your logs
data = [
    {"name": "Shweana and Vikram", "phone_id": "1020590777800328", "waba_id": "910991641872001", "number": "+919769600638"},
    {"name": "Ananya & Mudit", "phone_id": "149080968288848", "waba_id": "120550457817371", "number": "+918591910540"},
    {"name": "Rhea and Arjun", "phone_id": "243070572230822", "waba_id": "220783014462570", "number": "+919819114737"},
    {"name": "Vinisha and Vedang", "phone_id": "317550154772764", "waba_id": "305593562635092", "number": "+919820850574"},
    {"name": "A New Knot", "phone_id": "870641679456253", "waba_id": "1438091177259934", "number": "+919987469537"},
    {"name": "Aashreen & Shaurya", "phone_id": "403963616127926", "waba_id": "337583966111129", "number": "+919769600802"},
]

system_token = "EAAWufBTFZADEBQUZB1xh1JKtKEPNx8rMko4P2FabP5mXVJT9or5Jw430mm5oqYuoDhCPasFqd1TsDP0VEWNlE4YZB5z63iFNq83vyDkKA8ngqUgBTwBiTQ9FnsU1Uu6WzkrDWl01ApwPeTgmrsZBMhQBIOciTHS12bwtjHf00nWu1vKca34zNikJi5nCkYMLSwZDZD"

print("--- Syncing WhatsApp Business Accounts ---")

for item in data:
    # 1. Create/Update WABA
    waba, _ = WhatsAppBusinessAccount.objects.update_or_create(
        waba_id=item["waba_id"],
        defaults={"name": f"{item['name']} Account", "is_active": True}
    )
    
    # 2. Create/Update Phone Number
    WhatsAppPhoneNumber.objects.update_or_create(
        phone_number_id=item["phone_id"],
        defaults={
            "business_account": waba,
            "display_phone_number": item["number"],
            "verified_name": item["name"],
            "waba_id": item["waba_id"],
            "is_active": True,
            "is_default": (item["phone_id"] == "1020590777800328")
        }
    )
    print(f"✅ Linked {item['name']} to WABA {item['waba_id']}")

print("\n🚀 Full Sync Complete! You should now see all accounts in Django Admin.")
