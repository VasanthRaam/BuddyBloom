from supabase import create_client as _cc
from app.core.config import settings

def main():
    admin_client = _cc(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
    print("Listing users...")
    try:
        resp = admin_client.auth.admin.list_users()
        print("Response type:", type(resp))
        # Print attributes of the response object
        print("Attributes:", dir(resp))
        
        users_list = getattr(resp, 'users', resp)
        print("Users list length:", len(users_list))
        
        for idx, u in enumerate(users_list):
            email = getattr(u, 'email', None)
            uid = getattr(u, 'id', None)
            print(f"[{idx}] ID: {uid}, Email: {email}")
            
    except Exception as e:
        print("Failed to list users:", e)

if __name__ == "__main__":
    main()
