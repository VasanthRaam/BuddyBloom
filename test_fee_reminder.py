import asyncio
import httpx
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from app.db.database import AsyncSessionLocal
from app.db.models import User, FeePayment, Notification
from app.core.config import settings
from jose import jwt
from datetime import datetime, timedelta

def generate_test_token(user_id: str, email: str, role: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "exp": datetime.utcnow() + timedelta(hours=1)
    }
    return jwt.encode(payload, settings.SUPABASE_JWT_SECRET, algorithm="HS256")

async def test_fee_reminder_endpoint():
    async with AsyncSessionLocal() as db:
        # 1. Fetch an admin user
        res = await db.execute(select(User).where(User.role == 'admin').limit(1))
        admin = res.scalars().first()
        if not admin:
            print("❌ Verification Failed: No admin user found in database.")
            return
            
        print(f"ℹ️ Found admin user: {admin.email}")
        
        # 2. Fetch a pending fee payment
        res_fee = await db.execute(
            select(FeePayment)
            .where(FeePayment.status == 'pending')
            .options(selectinload(FeePayment.user))
            .limit(1)
        )
        fee = res_fee.scalars().first()
        if not fee:
            print("⚠️ No pending fee payment found in the database. Creating a mock one for testing...")
            # Let's find any student user to assign this mock fee to
            res_student = await db.execute(select(User).where(User.role == 'student').limit(1))
            student = res_student.scalars().first()
            if not student:
                # Try parent user
                res_parent = await db.execute(select(User).where(User.role == 'parent').limit(1))
                student = res_parent.scalars().first()
            
            if not student:
                print("❌ Verification Failed: No student or parent user found to attach a fee payment to.")
                return
            
            # Create a mock pending fee payment
            fee = FeePayment(
                user_id=student.id,
                amount=2500.0,
                due_date=datetime.utcnow() + timedelta(days=10),
                status='pending'
            )
            db.add(fee)
            await db.commit()
            await db.refresh(fee)
            print(f"ℹ️ Mock pending fee payment created with ID: {fee.id} for user: {student.email or student.full_name}")

        print(f"ℹ️ Testing reminder on pending fee ID: {fee.id} (Amount: ₹{fee.amount}, User ID: {fee.user_id})")

        # 3. Create auth token for admin
        role_str = str(admin.role.value) if hasattr(admin.role, 'value') else str(admin.role)
        access_token = generate_test_token(str(admin.id), admin.email, role_str)
        headers = {"Authorization": f"Bearer {access_token}"}
        
        # 4. Invoke API endpoint
        async with httpx.AsyncClient() as client:
            url = f"http://localhost:8000/api/v1/fees/{fee.id}/remind"
            print(f"ℹ️ Sending POST request to: {url}")
            try:
                resp = await client.post(url, headers=headers)
                print(f"ℹ️ API Response Status: {resp.status_code}")
                print(f"ℹ️ API Response Body: {resp.text}")
                
                assert resp.status_code == 200, f"Expected status 200, got {resp.status_code}"
                response_data = resp.json()
                assert response_data.get("status") == "success", f"Expected success status, got {response_data}"
                print("✅ API Endpoint returned success!")
            except Exception as e:
                print(f"❌ API Call failed: {e}")
                return

        # 5. Check if notification record was created in the database
        res_notif = await db.execute(
            select(Notification)
            .where(Notification.user_id == fee.user_id)
            .order_by(Notification.created_at.desc())
            .limit(1)
        )
        notif = res_notif.scalars().first()
        if notif and "Pending" in notif.title:
            print(f"✅ Notification verified in DB: '{notif.title}' - '{notif.message}'")
        else:
            print(f"❌ Notification NOT found or mismatched in DB. Latest: {notif.title if notif else 'None'}")

if __name__ == "__main__":
    asyncio.run(test_fee_reminder_endpoint())
