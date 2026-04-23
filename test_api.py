import asyncio
import httpx
from sqlalchemy.future import select
from app.db.database import AsyncSessionLocal
from app.db.models import User
from app.core.security import create_access_token
from datetime import timedelta

async def test_api():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(User).where(User.role == 'admin').limit(1))
        admin = res.scalars().first()
        if not admin:
            print("No admin user found!")
            return
            
        print(f"Admin: {admin.email}")
        
        # Create token
        access_token_expires = timedelta(minutes=60)
        access_token = create_access_token(
            subject=str(admin.id), expires_delta=access_token_expires
        )
        print(f"Token created")
        
        headers = {"Authorization": f"Bearer {access_token}"}
        
        async with httpx.AsyncClient() as client:
            print("Fetching /api/v1/batches/")
            resp = await client.get("http://localhost:8000/api/v1/batches/", headers=headers)
            print(f"Status: {resp.status_code}")
            print(f"Body: {resp.text}")
            
            if resp.status_code == 200:
                batches = resp.json()
                if batches:
                    batch_id = batches[0]['id']
                    print(f"\nFetching /api/v1/batches/{batch_id}/students")
                    resp2 = await client.get(f"http://localhost:8000/api/v1/batches/{batch_id}/students", headers=headers)
                    print(f"Status: {resp2.status_code}")
                    print(f"Body: {resp2.text}")
                else:
                    print("Batches array is empty")

if __name__ == "__main__":
    asyncio.run(test_api())
