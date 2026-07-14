import os
import django
import requests

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ANK.settings')
django.setup()

from MessageTemplates.models import WhatsAppPhoneNumber

print("--- Querying Meta Graph API for Phone Numbers ---")

# We'll use the active WABA IDs and their tokens from the database.
# Since we might have multiple phone numbers in the DB sharing the same WABA and token,
# we'll group by WABA ID to avoid duplicate requests.

checked_wabas = set()
phone_numbers = WhatsAppPhoneNumber.objects.filter(is_active=True)

for phone in phone_numbers:
    waba_id = phone.waba_id
    access_token = phone.get_access_token()
    
    if not waba_id or not access_token:
        print(f"⚠️  Skipping {phone.display_phone_number} - Missing WABA ID or Access Token in DB")
        continue
        
    if waba_id in checked_wabas:
        continue
        
    checked_wabas.add(waba_id)
    print(f"\n🔍 Checking WABA ID: {waba_id} (using token from phone {phone.display_phone_number})")
    
    url = f"https://graph.facebook.com/v20.0/{waba_id}/phone_numbers"
    try:
        res = requests.get(url, params={"access_token": access_token}, timeout=10)
        data = res.json()
        
        if res.ok:
            meta_numbers = data.get("data", [])
            if not meta_numbers:
                print("   ❌ No phone numbers found in this WABA on Meta's side.")
            else:
                print(f"   ✅ Found {len(meta_numbers)} phone number(s) on Meta:")
                for n in meta_numbers:
                    print(f"      - ID: {n.get('id')} | Number: {n.get('display_phone_number')} | Status: {n.get('status')} | Quality: {n.get('quality_rating')}")
        else:
            print(f"   ❌ Meta API Error: {data.get('error', {}).get('message', 'Unknown Error')}")
            print(f"      Error Details: {data}")
    except Exception as e:
        print(f"   ❌ Request failed: {e}")

print("\n🚀 Check Complete!")
