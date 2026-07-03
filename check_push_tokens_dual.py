import requests

def check_db(name, url, key):
    headers = {
        'apikey': key,
        'Authorization': f'Bearer {key}',
        'Content-Type': 'application/json'
    }
    print(f"[i] Checking {name} Database ({url})...")
    try:
        query_url = f"{url}/rest/v1/user_push_tokens?select=*,users(email)"
        res = requests.get(query_url, headers=headers)
        res.raise_for_status()
        tokens = res.json()
        print(f"--- Registered Push Tokens in {name} ({len(tokens)}) ---")
        for t in tokens:
            email = t.get('users', {}).get('email', 'Unknown') if t.get('users') else 'Unknown'
            token = t.get('push_token', '')
            device = t.get('device_type', 'unknown')
            print(f"User: {email} | Token: {token[:40]}... | Device: {device}")
        print("------------------------------------\n")
    except Exception as e:
        print(f"[-] REST Request failed for {name}: {e}\n")

# Check Dev
check_db(
    "Dev DB", 
    "https://dgmmkirxdpflxniqpako.supabase.co", 
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRnbW1raXJ4ZHBmbHhuaXFwYWtvIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODI5ODAzMTgsImV4cCI6MjA5ODU1NjMxOH0.G0rS7AuSzWQJCEUllYDLRBDeXG-mDCq9uepxSCDANRc"
)

# Check Prod
check_db(
    "Prod DB", 
    "https://kzjtserfhbkgzvcfpoyx.supabase.co", 
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imt6anRzZXJmaGJrZ3p2Y2Zwb3l4Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3Njc1NDg2MCwiZXhwIjoyMDkyMzMwODYwfQ.SY9dZB5V8r1mfG-hnpA0kXU0xc7jFxfJpHO4ibAM3ZU"
)
