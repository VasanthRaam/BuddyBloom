import requests

def check_pending(name, url, key):
    headers = {
        'apikey': key,
        'Authorization': f'Bearer {key}',
        'Content-Type': 'application/json'
    }
    print(f"[i] Checking {name} for pending registrations ({url})...")
    try:
        query_url = f"{url}/rest/v1/pending_registrations?select=id,email,status,created_at&limit=5&order=created_at.desc"
        res = requests.get(query_url, headers=headers)
        res.raise_for_status()
        rows = res.json()
        print(f"--- Recent Pending Registrations in {name} ({len(rows)}) ---")
        for r in rows:
            print(f"ID: {r.get('id')} | Email: {r.get('email')} | Status: {r.get('status')} | Created At: {r.get('created_at')}")
        print("------------------------------------\n")
    except Exception as e:
        print(f"[-] REST Request failed for {name}: {e}\n")

# Check Dev
check_pending(
    "Dev DB", 
    "https://dgmmkirxdpflxniqpako.supabase.co", 
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJinc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRnbW1raXJ4ZHBmbHhuaXFwYWtvIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODI5ODAzMTgsImV4cCI6MjA5ODU1NjMxOH0.G0rS7AuSzWQJCEUllYDLRBDeXG-mDCq9uepxSCDANRc"
)

# Check Prod
check_pending(
    "Prod DB", 
    "https://kzjtserfhbkgzvcfpoyx.supabase.co", 
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imt6anRzZXJmaGJrZ3p2Y2Zwb3l4Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3Njc1NDg2MCwiZXhwIjoyMDkyMzMwODYwfQ.SY9dZB5V8r1mfG-hnpA0kXU0xc7jFxfJpHO4ibAM3ZU"
)
