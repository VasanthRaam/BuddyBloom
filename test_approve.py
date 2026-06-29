import asyncio
import uuid
from app.db.database import AsyncSessionLocal
from app.db.models import PendingRegistration, User, UserRole, Student, Batch, Enrollment
from app.core.config import settings
from supabase import create_client as _cc
from sqlalchemy.future import select

async def test_approve_task(p_id_str):
    supabase = _cc(settings.SUPABASE_URL, settings.SUPABASE_KEY)
    
    async with AsyncSessionLocal() as session:
        # 1. Fetch pending record
        p_res = await session.execute(
            select(PendingRegistration).where(PendingRegistration.id == uuid.UUID(p_id_str))
        )
        p = p_res.scalars().first()
        if not p:
            print("Pending registration not found!")
            return
            
        saved_password = p.hashed_temp_password
        print(f"Pending registration found for {p.email}. Status: {p.status}. Role: {p.role}")
        
        # 2. Supabase Auth account creation
        supabase_user_id = None
        if saved_password == "GOOGLE_AUTH_PLACEHOLDER":
            supabase_user_id = p.id
            print(f"[APPROVE] Google user detected. Supabase ID: {supabase_user_id}")
        else:
            try:
                print(f"[APPROVE] Checking if user already exists by signing in...")
                sign_in_check = supabase.auth.sign_in_with_password({
                    "email": p.email,
                    "password": saved_password,
                })
                supabase_user_id = sign_in_check.user.id
                supabase.auth.sign_out()
                print(f"[APPROVE] Existing user signed in successfully: {supabase_user_id}")
            except Exception as e:
                print(f"[APPROVE] sign_in_with_password failed (expected for new users): {e}")
                
            if not supabase_user_id:
                try:
                    if settings.SUPABASE_SERVICE_KEY:
                        print(f"[APPROVE] Initializing admin client for email: {p.email}...")
                        admin_client = _cc(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
                        auth_response = admin_client.auth.admin.create_user({
                            "email": p.email,
                            "password": saved_password,
                            "email_confirm": True,
                        })
                        supabase_user_id = auth_response.user.id
                        print(f"[APPROVE] Created user successfully via Admin: {supabase_user_id}")
                    else:
                        print(f"[APPROVE] Service key not found, using sign_up for: {p.email}...")
                        auth_response = supabase.auth.sign_up({
                            "email": p.email,
                            "password": saved_password,
                        })
                        if auth_response.user:
                            supabase_user_id = auth_response.user.id
                            print(f"[APPROVE] Signed up user successfully: {supabase_user_id}")
                except Exception as e:
                    print(f"[APPROVE] create_user/sign_up failed with error: {e}")
                    err = str(e)
                    if "already exists" in err.lower() or "already registered" in err.lower() or "already been registered" in err.lower():
                        try:
                            print("[APPROVE] User already exists in Supabase. Attempting to list users...")
                            admin_client_to_use = admin_client if 'admin_client' in locals() else supabase
                            all_users_resp = admin_client_to_use.auth.admin.list_users()
                            users_list = getattr(all_users_resp, 'users', all_users_resp)
                            for u in users_list:
                                u_email = getattr(u, 'email', None) or (isinstance(u, dict) and u.get('email'))
                                if u_email and u_email.lower() == p.email.lower():
                                    supabase_user_id = getattr(u, 'id', None) or (isinstance(u, dict) and u.get('id'))
                                    print(f"[APPROVE] Found existing user ID: {supabase_user_id}")
                                    break
                        except Exception as list_err:
                            print(f"[APPROVE] list_users fallback failed: {list_err}")

        if not supabase_user_id:
            print(f"[APPROVE] Failed to obtain Supabase ID for {p.email}.")
            return

        print(f"[APPROVE] Proceeding to create User record in DB...")
        # 3. Create local User profile
        new_user = User(
            id=supabase_user_id,
            full_name=p.full_name,
            email=p.email,
            phone=p.phone,
            role=p.role,
            is_approved=True,
            dob=p.dob,
            education_qualification=p.education_qualification,
            profile_picture=p.profile_picture,
        )
        session.add(new_user)
        await session.flush()
        print(f"[APPROVE] Local User record created.")

        # 4. Enrollments / Assignments
        if p.role == UserRole.student:
            student_profile = Student(
                id=uuid.uuid4(),
                user_id=new_user.id,
                parent_id=new_user.id,
                first_name=p.full_name.split()[0],
                last_name=" ".join(p.full_name.split()[1:]) if len(p.full_name.split()) > 1 else "",
                mother_name=p.mother_name,
                father_name=p.father_name,
                parent_phone_number=p.parent_phone_number,
                date_of_birth=p.dob,
            )
            session.add(student_profile)
            await session.flush()
            print(f"[APPROVE] Local Student record created.")
            
            if p.selected_batch_ids:
                for b_id in p.selected_batch_ids:
                    enrollment = Enrollment(
                        id=uuid.uuid4(),
                        student_id=student_profile.id,
                        batch_id=b_id
                    )
                    session.add(enrollment)
                    print(f"[APPROVE] Enrolled in batch {b_id}.")
                    
        p.status = "approved"
        await session.commit()
        print(f"[APPROVE] Committed successfully!")

if __name__ == "__main__":
    asyncio.run(test_approve_task("ccc25c8c-4463-44f5-a1c5-97953a9577e0"))
