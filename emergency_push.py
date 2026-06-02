import httpx
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

async def send_push_via_api(email):
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    
    print(f"Looking for user {email} via Web API...")
    
    async with httpx.AsyncClient() as client:
        # 1. Get User ID
        res = await client.get(f"{SUPABASE_URL}/rest/v1/users?email=eq.{email}&select=id,full_name", headers=headers)
        users = res.json()
        
        if not users:
            print(f"User {email} not found.")
            return
            
        user_id = users[0]['id']
        name = users[0]['full_name']
        print(f"Found {name} (ID: {user_id})")
        
        # 2. Get Push Tokens
        res = await client.get(f"{SUPABASE_URL}/rest/v1/user_push_tokens?user_id=eq.{user_id}&select=push_token", headers=headers)
        tokens = [t['push_token'] for t in res.json()]
        
        if not tokens:
            print(f"No push tokens found in DB for {email}. Are you sure you're logged in on the phone?")
            return
            
        print(f"Sending test to {len(tokens)} tokens via Expo...")
        
        # 3. Send via Expo
        expo_url = "https://exp.host/--/api/v2/push/send"
        messages = [{
            "to": token,
            "title": "BuddyBloom Test",
            "body": f"Your login is {email}. This notification reached you successfully!",
            "sound": "default",
            "channelId": "default"
        } for token in tokens]
        
        res = await client.post(expo_url, json=messages)
        print(f"Expo Response: {res.text}")
        print("\nDONE. Check your phone!")

if __name__ == "__main__":
    import sys
    target_email = sys.argv[1] if len(sys.argv) > 1 else "vasanth@gmail.com"
    asyncio.run(send_push_via_api(target_email))
