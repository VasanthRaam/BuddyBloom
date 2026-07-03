import requests

SUPABASE_URL = 'https://dgmmkirxdpflxniqpako.supabase.co'
SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRnbW1raXJ4ZHBmbHhuaXFwYWtvIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODI5ODAzMTgsImV4cCI6MjA5ODU1NjMxOH0.G0rS7AuSzWQJCEUllYDLRBDeXG-mDCq9uepxSCDANRc'

headers = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json'
}

print("[i] Fetching in-app notifications from Dev Database via REST API...")
try:
    url = f"{SUPABASE_URL}/rest/v1/notifications?select=*,users(email)&limit=10&order=created_at.desc"
    res = requests.get(url, headers=headers)
    res.raise_for_status()
    notifs = res.json()
    
    print(f"\n--- Recent Notifications ({len(notifs)}) ---")
    for n in notifs:
        email = n.get('users', {}).get('email', 'Unknown') if n.get('users') else 'Unknown'
        title = n.get('title', '')
        message = n.get('message', '')
        is_read = n.get('is_read', False)
        print(f"To: {email} | Title: {title} | Msg: {message} | Read: {is_read}")
    print("------------------------------------\n")
except Exception as e:
    print(f"[-] REST Request failed: {e}")
