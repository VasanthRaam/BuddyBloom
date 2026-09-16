import uuid
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException
from app.db.models import User, Student, Enrollment, UserRole, Batch, Course, Notification
from app.core.config import settings
from supabase import create_client as _cc
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)

class UserCreationService:
    @staticmethod
    async def create_active_user(
        db: AsyncSession,
        email: str,
        password: str,
        full_name: str,
        phone: str,
        role: UserRole,
        selected_course_ids: list[str] = None,
        selected_batch_ids: list[str] = None,
        mother_name: str = None,
        father_name: str = None,
        parent_phone_number: str = None,
        dob=None,
        education_qualification: str = None,
        profile_picture: str = None,
    ) -> User:
        """
        Creates a user directly in Supabase Auth and Local DB.
        Bypasses pending registration.
        """
        # 1. Check if user already exists
        existing = await db.execute(select(User).where(User.email == email))
        if existing.scalars().first():
            raise HTTPException(status_code=409, detail="A user with this email is already registered.")

        # 2. Supabase Auth creation
        supabase_user_id = None
        if not settings.SUPABASE_SERVICE_KEY:
            raise HTTPException(status_code=500, detail="Service key not configured.")

        try:
            admin_client = _cc(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
            auth_response = admin_client.auth.admin.create_user({
                "email": email,
                "password": password,
                "email_confirm": True,
            })
            supabase_user_id = auth_response.user.id
            logger.info(f"[CREATE-USER] Created Supabase user successfully: {supabase_user_id}")
        except Exception as e:
            logger.error(f"[CREATE-USER] Supabase user creation failed: {e}", exc_info=True)
            err = str(e)
            if any(msg in err.lower() for msg in ["already exists", "already registered", "already been registered"]):
                # Try to fetch existing Supabase user
                try:
                    all_users_resp = admin_client.auth.admin.list_users()
                    users_list = getattr(all_users_resp, 'users', all_users_resp)
                    for u in users_list:
                        u_email = getattr(u, 'email', None) or (isinstance(u, dict) and u.get('email'))
                        if u_email and u_email.lower() == email.lower():
                            supabase_user_id = getattr(u, 'id', None) or (isinstance(u, dict) and u.get('id'))
                            break
                except Exception as list_err:
                    pass
            if not supabase_user_id:
                raise HTTPException(status_code=400, detail=f"Failed to create user in Auth provider: {str(e)}")

        # 3. Create local User profile
        new_user = User(
            id=supabase_user_id,
            full_name=full_name,
            email=email,
            phone=phone,
            role=role,
            is_approved=True,
            dob=dob,
            education_qualification=education_qualification,
            profile_picture=profile_picture,
        )
        db.add(new_user)
        await db.flush()

        # 4. Role-specific profile
        if role == UserRole.student:
            student_profile = Student(
                id=uuid.uuid4(),
                user_id=new_user.id,
                parent_id=new_user.id,
                first_name=full_name.split()[0],
                last_name=" ".join(full_name.split()[1:]) if len(full_name.split()) > 1 else "",
                mother_name=mother_name,
                father_name=father_name,
                parent_phone_number=parent_phone_number,
                date_of_birth=dob,
            )
            db.add(student_profile)
            await db.flush()

            if selected_batch_ids:
                for b_id in selected_batch_ids:
                    enrollment = Enrollment(
                        id=uuid.uuid4(),
                        student_id=student_profile.id,
                        batch_id=uuid.UUID(str(b_id))
                    )
                    db.add(enrollment)
        
        elif role == UserRole.teacher:
            if selected_batch_ids:
                for b_id in selected_batch_ids:
                    res = await db.execute(select(Batch).where(Batch.id == uuid.UUID(str(b_id))))
                    batch = res.scalars().first()
                    if batch:
                        batch.teacher_id = new_user.id

        await db.commit()
        await db.refresh(new_user)
        return new_user
