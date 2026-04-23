"""
Test script: simulates exactly what the approve endpoint does.
Run: venv\Scripts\python test_approve.py <pending_id>
"""
import asyncio
import sys
from supabase import create_client

async def test(pending_id: str):
    # Load settings
    import os, dotenv
    dotenv.load_dotenv()
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_KEY"]
    service_key = os.environ.get("SUPABASE_SERVICE_KEY", "")

    print(f"SUPABASE_URL:         {url}")
    print(f"SUPABASE_KEY:         {key[:20]}...")
    print(f"SUPABASE_SERVICE_KEY: {'SET' if service_key else 'NOT SET'}")
    print()

    # Fetch pending record
    from sqlalchemy.future import select
    from app.db.database import AsyncSessionLocal
    from app.db.models import PendingRegistration

    async with AsyncSessionLocal() as db:
        res = await db.execute(
            select(PendingRegistration).where(PendingRegistration.id == pending_id)
        )
        pending = res.scalars().first()
        if not pending:
            print(f"ERROR: No pending registration with id={pending_id}")
            return

        print(f"Found pending: {pending.email} ({pending.role}) status={pending.status}")
        email = pending.email
        password = pending.hashed_temp_password

        if password == "REDACTED":
            print("ERROR: Password already redacted — this registration was already processed.")
            return

    # Try creating Supabase Auth user
    print(f"\nAttempting supabase.auth.sign_up for {email}...")
    client = create_client(url, key)
    try:
        resp = client.auth.sign_up({"email": email, "password": password})
        print(f"SUCCESS: Supabase user created with id={resp.user.id}")
    except Exception as e:
        print(f"FAILED: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        print("\nTip: If the error is about email confirmation, disable it in:")
        print("  Supabase Dashboard -> Authentication -> Settings -> Confirm email = OFF")

if __name__ == "__main__":
    pid = sys.argv[1] if len(sys.argv) > 1 else input("Enter pending_id: ").strip()
    asyncio.run(test(pid))
