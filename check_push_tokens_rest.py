import requests

SUPABASE_URL = 'https://dgmmkirxdpflxniqpako.supabase.co'
SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRnbW1raXJ4ZHBmbHhuaXFwYWtvIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODI5ODAzMTgsImV4cCI6MjA5ODU1NjMxOH0.G0rS7AuSzWQJCEUllYDLRBDeXG-mDCq9uepxSCDANRc'

headers = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json'
}

# Fetch user push tokens
print("[i] Fetching registered push tokens from Dev Database via REST API...")
try:
    # Query join user_push_tokens and users
    url = f"{SUPABASE_URL}/rest/v1/user_push_tokens?select=*,users(email)"
    res = requests.get(url, headers=headers)
    res.raise_for_status()
    tokens = res.json()
    
    print(f"\n--- Registered Push Tokens ({len(tokens)}) ---")
    for t in tokens:
        email = t.get('users', {}).get('email', 'Unknown') if t.get('users') else 'Unknown'
        token = t.get('push_token', '')
        device = t.get('device_type', 'unknown')
        print(f"User: {email} | Token: {token[:30]}... | Device: {device}")
    print("------------------------------------\n")
except Exception as e:
    print(f"[-] REST Request failed: {e}")
