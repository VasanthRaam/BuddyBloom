import requests

DEV_URL = "https://dgmmkirxdpflxniqpako.supabase.co"
DEV_SERVICE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRnbW1raXJ4ZHBmbHhuaXFwYWtvIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4Mjk4MDMxOCwiZXhwIjoyMDk4NTU2MzE4fQ.dPfGd0ulOS-RtStukHorUParEm0NUGxxf1kabp_H_bA'

headers = {
    'apikey': DEV_SERVICE_KEY,
    'Authorization': f'Bearer {DEV_SERVICE_KEY}',
    'Content-Type': 'application/json'
}

print("[i] Checking users in Dev Database...")
try:
    url = f"{DEV_URL}/rest/v1/users?select=id,email,role,full_name"
    res = requests.get(url, headers=headers)
    res.raise_for_status()
    users = res.json()
    print(f"--- Users in Database ({len(users)}) ---")
    for u in users:
        print(f"  ID: {u.get('id')} | Email: {u.get('email')} | Role: {u.get('role')} | Name: {u.get('full_name')}")
    print("------------------------------------\n")
except Exception as e:
    print(f"[-] Error: {e}\n")
