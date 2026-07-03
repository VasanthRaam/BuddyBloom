import requests

DEV_URL = "https://dgmmkirxdpflxniqpako.supabase.co"
DEV_SERVICE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRnbW1raXJ4ZHBmbHhuaXFwYWtvIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4Mjk4MDMxOCwiZXhwIjoyMDk4NTU2MzE4fQ.dPfGd0ulOS-RtStukHorUParEm0NUGxxf1kabp_H_bA'

PROD_URL = "https://kzjtserfhbkgzvcfpoyx.supabase.co"
PROD_SERVICE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imt6anRzZXJmaGJrZ3p2Y2Zwb3l4Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3Njc1NDg2MCwiZXhwIjoyMDkyMzMwODYwfQ.SY9dZB5V8r1mfG-hnpA0kXU0xc7jFxfJpHO4ibAM3ZU'

def check_db_bypass_rls(name, url, key):
    headers = {
        'apikey': key,
        'Authorization': f'Bearer {key}',
        'Content-Type': 'application/json'
    }
    print(f"[i] Checking {name} ({url}) bypassing RLS...")
    try:
        # Query registrations
        q_url = f"{url}/rest/v1/pending_registrations?select=id,email,status,created_at&limit=5&order=created_at.desc"
        res = requests.get(q_url, headers=headers)
        res.raise_for_status()
        rows = res.json()
        print(f"--- Recent Pending Registrations ({len(rows)}) ---")
        for r in rows:
            print(f"  ID: {r.get('id')} | Email: {r.get('email')} | Status: {r.get('status')} | Created At: {r.get('created_at')}")
            
        # Query push tokens
        t_url = f"{url}/rest/v1/user_push_tokens?select=*,users(email)"
        res_t = requests.get(t_url, headers=headers)
        res_t.raise_for_status()
        tokens = res_t.json()
        print(f"--- Registered Push Tokens ({len(tokens)}) ---")
        for t in tokens:
            email = t.get('users', {}).get('email', 'Unknown') if t.get('users') else 'Unknown'
            token = t.get('push_token', '')
            device = t.get('device_type', 'unknown')
            user_id = t.get('user_id', 'unknown')
            print(f"  User: {email} (ID: {user_id}) | Token: {token[:35]}... | Device: {device}")
        print("------------------------------------\n")
    except Exception as e:
        print(f"[-] Error: {e}\n")

check_db_bypass_rls("Dev DB", DEV_URL, DEV_SERVICE_KEY)
check_db_bypass_rls("Prod DB", PROD_URL, PROD_SERVICE_KEY)
