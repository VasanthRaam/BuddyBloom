"""
Authentication endpoints:
  POST /auth/register        — public, creates PendingRegistration + notifies admins
  POST /auth/login           — public, verifies Supabase + checks is_approved
  GET  /auth/pending         — admin only, list pending registrations
  POST /auth/approve/{id}    — admin only, creates Supabase Auth user + local User + deletes pending
  POST /auth/reject/{id}     — admin only, marks pending as rejected with optional reason
"""
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, EmailStr
from supabase import create_client, Client
from app.core.config import settings
from app.db.database import get_db
from app.db.models import User, UserRole, PendingRegistration, Notification
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import uuid

router = APIRouter()

supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

# ── Pydantic schemas ──────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    full_name: str
    email: EmailStr
    phone: str | None = None
    password: str
    role: str  # "teacher" | "student" | "parent"
    course_ids: list[uuid.UUID] | None = []
    batch_ids: list[uuid.UUID] | None = []
    push_token: str | None = None
    supabase_uid: uuid.UUID | None = None

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class ApproveRequest(BaseModel):
    pass  # No body needed

class RejectRequest(BaseModel):
    reason: str | None = "No reason provided."

class GoogleSyncRequest(BaseModel):
    access_token: str
    email: EmailStr
    full_name: str

# ── Helper ────────────────────────────────────────────────────────────────────

def _role_value(role) -> str:
    return role.value if hasattr(role, "value") else str(role)

# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/courses-batches")
async def get_courses_batches(db: AsyncSession = Depends(get_db)):
    """Fetch all available courses and their batches for registration."""
    from app.db.models import Course, Batch
    res = await db.execute(select(Course))
    courses = res.scalars().all()
    
    output = []
    for c in courses:
        b_res = await db.execute(select(Batch).where(Batch.course_id == c.id))
        batches = b_res.scalars().all()
        output.append({
            "id": str(c.id),
            "name": c.name,
            "batches": [{"id": str(b.id), "name": b.name} for b in batches]
        })
    return output

from fastapi import APIRouter, HTTPException, Depends, status, BackgroundTasks

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequest, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    """
    Step 1 of sign-up: store details in pending_registrations and alert admins.
    Supabase Auth account is NOT created yet — that happens on admin approval.
    """
    # Validate role — only teacher, student, parent can self-register
    allowed_roles = {"teacher", "student", "parent"}
    if request.role not in allowed_roles:
        raise HTTPException(status_code=400, detail="Invalid role. Allowed: teacher, student, parent")

    # Check if email already exists in pending_registrations
    existing_pending = await db.execute(
        select(PendingRegistration).where(PendingRegistration.email == request.email)
    )
    if existing_pending.scalars().first():
        raise HTTPException(status_code=409, detail="A registration request for this email is already pending.")

    # Check if email already exists in the main users table
    existing_user = await db.execute(
        select(User).where(User.email == request.email)
    )
    if existing_user.scalars().first():
        raise HTTPException(status_code=409, detail="This email is already registered. Please login.")

    # Store the pending registration (password stored temporarily for admin to create Supabase account)
    pending = PendingRegistration(
        id=request.supabase_uid if request.supabase_uid else uuid.uuid4(),
        full_name=request.full_name,
        email=request.email,
        phone=request.phone,
        hashed_temp_password=request.password,
        role=UserRole(request.role),
        status="pending",
        selected_course_ids=request.course_ids,
        selected_batch_ids=request.batch_ids,
        push_token=request.push_token,
    )
    db.add(pending)
    await db.flush()

    # Trigger notifications in background
    async def notify_admins(pending_id_str, full_name, role_str):
        from app.db.database import AsyncSessionLocal
        from app.services.notification_service import NotificationService
        from app.db.models import User, UserRole, Notification
        import uuid
        async with AsyncSessionLocal() as session:
            admin_res = await session.execute(select(User).where(User.role == UserRole.admin))
            admins = admin_res.scalars().all()
            for admin in admins:
                notif = Notification(
                    id=uuid.uuid4(),
                    user_id=admin.id,
                    title="New Registration Request",
                    message=f"{full_name} ({role_str}) has requested to join BuddyBloom. Tap to review.",
                    link_to=f"PendingApproval:{pending_id_str}",
                    is_read=False,
                )
                session.add(notif)
                await NotificationService.send_push_notification(
                    session, admin.id, "New Registration Request 👤",
                    f"{full_name} ({role_str}) has requested to join. Tap to review.",
                    {"type": "registration", "id": pending_id_str}
                )
            await session.commit()

    await db.commit()
    background_tasks.add_task(notify_admins, str(pending.id), request.full_name, request.role)

    return {
        "message": "Registration submitted. An admin will review your request. You will be able to login once approved.",
        "pending_id": str(pending.id),
    }


@router.post("/login")
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Authenticate via Supabase then verify the local profile is approved.
    """
    from sqlalchemy import func
    
    # 0. Check if user is pending registration FIRST.
    pend_res = await db.execute(
        select(PendingRegistration).where(func.lower(PendingRegistration.email) == func.lower(request.email))
    )
    pending = pend_res.scalars().first()
    if pending:
        if pending.status == "pending":
            raise HTTPException(
                status_code=403,
                detail="Your registration is pending admin approval. Please wait."
            )
        elif pending.status == "rejected":
            raise HTTPException(
                status_code=403,
                detail=f"Your registration was rejected. Reason: {pending.rejection_reason}"
            )

    # 1. Try Supabase auth
    try:
        response = supabase.auth.sign_in_with_password({
            "email": request.email,
            "password": request.password,
        })
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    supabase_id = response.user.id
    email = response.user.email

    # Convert string ID to UUID object to avoid DB type comparison issues
    try:
        supabase_uuid = uuid.UUID(str(supabase_id))
    except ValueError:
        supabase_uuid = None

    # 2. Fetch local profile — try by Supabase ID first, then fall back to email
    db_user = None
    if supabase_uuid:
        result = await db.execute(select(User).where(User.id == supabase_uuid))
        db_user = result.scalars().first()

    if not db_user:
        from sqlalchemy import func
        result = await db.execute(
            select(User).where(func.lower(User.email) == func.lower(email))
        )
        db_user = result.scalars().first()

    # 3. Edge-case: the user exists in Supabase Auth but NOT in our DB
    if not db_user:
        # Check if they have a pending registration
        pend_res = await db.execute(
            select(PendingRegistration).where(PendingRegistration.email == email)
        )
        pending = pend_res.scalars().first()
        if pending and pending.status == "pending":
            raise HTTPException(
                status_code=403,
                detail="Your registration is pending admin approval. Please wait."
            )
        if pending and pending.status == "rejected":
            raise HTTPException(
                status_code=403,
                detail=f"Your registration was rejected. Reason: {pending.rejection_reason}"
            )
        raise HTTPException(status_code=404, detail="User profile not found. Please contact the admin.")

    # 4. Check approval status
    if not db_user.is_approved:
        raise HTTPException(
            status_code=403,
            detail="Your account is pending admin approval. You will be notified once approved."
        )

    user_data = {
        "id": str(db_user.id),
        "email": db_user.email,
        "role": _role_value(db_user.role),
        "full_name": db_user.full_name,
        "created_at": db_user.created_at.isoformat() if db_user.created_at else None,
    }

    return {
        "access_token": response.session.access_token,
        "token_type": "bearer",
        "user": user_data,
    }

@router.post("/google-sync")
async def google_sync(request: GoogleSyncRequest, db: AsyncSession = Depends(get_db)):
    """
    Sync a Google-authenticated user with our local database.
    If the user doesn't exist, return 404 so the app can redirect to Register.
    """
    from sqlalchemy import func
    print(f"[GOOGLE-SYNC] Syncing user email: {request.email}")
    
    # 1. Fetch local profile by email (case-insensitive)
    result = await db.execute(
        select(User).where(func.lower(User.email) == func.lower(request.email))
    )
    db_user = result.scalars().first()

    if not db_user:
        # Check if they have a pending registration
        pend_res = await db.execute(
            select(PendingRegistration).where(PendingRegistration.email == request.email)
        )
        pending = pend_res.scalars().first()
        if pending:
            if pending.status == "pending":
                raise HTTPException(status_code=403, detail="Your Google registration is pending admin approval.")
            if pending.status == "rejected":
                raise HTTPException(status_code=403, detail=f"Your registration was rejected. Reason: {pending.rejection_reason}")
        
        # Truly not found -> Trigger registration flow on mobile
        raise HTTPException(status_code=404, detail="Profile not found. Please complete registration.")

    # 2. Check approval status
    if not db_user.is_approved:
        raise HTTPException(
            status_code=403,
            detail="Your account is pending admin approval."
        )

    return {
        "user": {
            "id": str(db_user.id),
            "email": db_user.email,
            "role": _role_value(db_user.role),
            "full_name": db_user.full_name,
        }
    }


@router.get("/pending")
async def list_pending(db: AsyncSession = Depends(get_db)):
    """
    Returns all pending registration requests. Callable by admin.
    (Auth check is done in deps; we expose this publicly here and the
     mobile app restricts the screen to admin role.)
    """
    result = await db.execute(
        select(PendingRegistration)
        .where(PendingRegistration.status == "pending")
        .order_by(PendingRegistration.created_at.asc())
    )
    rows = result.scalars().all()
    return [
        {
            "id": str(r.id),
            "full_name": r.full_name,
            "email": r.email,
            "phone": r.phone,
            "role": _role_value(r.role),
            "created_at": r.created_at,
        }
        for r in rows
    ]


@router.post("/approve/{pending_id}")
async def approve_registration(
    pending_id: str, 
    background_tasks: BackgroundTasks, 
    db: AsyncSession = Depends(get_db)
):
    """
    Admin approves a registration:
    1. Instantly marks status as approved in DB so card disappears from UI.
    2. Spawns BackgroundTask to create Supabase Auth account and local profile.
    3. Triggers welcome push notification to new student/teacher.
    """
    pend_res = await db.execute(
        select(PendingRegistration).where(PendingRegistration.id == pending_id)
    )
    pending = pend_res.scalars().first()

    if not pending:
        raise HTTPException(status_code=404, detail="Pending registration not found.")
    if pending.status != "pending":
        raise HTTPException(status_code=409, detail=f"Registration is already {pending.status}.")

    # Guard: race condition — another admin already approved
    existing = await db.execute(select(User).where(User.email == pending.email))
    if existing.scalars().first():
        pending.status = "approved"
        pending.hashed_temp_password = "REDACTED"
        await db.commit()
        raise HTTPException(status_code=409, detail="A user with this email is already registered.")

    # Synchronously mark as approved and commit, so UI is unblocked immediately
    pending.status = "approved"
    await db.commit()

    async def process_approval_task(p_id_str):
        from app.db.database import AsyncSessionLocal
        from app.db.models import PendingRegistration, User, UserRole, Notification
        from app.core.config import settings
        from supabase import create_client as _cc
        import uuid
        
        async with AsyncSessionLocal() as session:
            # 1. Fetch pending record again inside background session
            p_res = await session.execute(
                select(PendingRegistration).where(PendingRegistration.id == uuid.UUID(p_id_str))
            )
            p = p_res.scalars().first()
            if not p:
                return
                
            saved_password = p.hashed_temp_password
            
            # 2. Supabase Auth account creation
            supabase_user_id = None
            if saved_password == "GOOGLE_AUTH_PLACEHOLDER":
                # For Google users, they already exist in Supabase Auth
                # The pending ID is their Supabase User ID
                supabase_user_id = p.id
                print(f"[APPROVE] Google user detected. Using pending ID as Supabase ID: {supabase_user_id}")
            else:
                try:
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
                            print(f"[APPROVE] Created user successfully: {supabase_user_id}")
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
                        import traceback
                        traceback.print_exc()
                        err = str(e)
                        if "already exists" in err.lower() or "already registered" in err.lower():
                            try:
                                print("[APPROVE] User already exists in Supabase. Attempting to list users and find ID...")
                                admin_client_to_use = admin_client if 'admin_client' in locals() else supabase
                                all_users_resp = admin_client_to_use.auth.admin.list_users()
                                users_list = getattr(all_users_resp, 'users', all_users_resp)
                                for u in users_list:
                                    if getattr(u, 'email', None) == p.email or (isinstance(u, dict) and u.get('email') == p.email):
                                        supabase_user_id = getattr(u, 'id', None) or (isinstance(u, dict) and u.get('id'))
                                        print(f"[APPROVE] Found existing user ID: {supabase_user_id}")
                                        break
                            except Exception as list_err:
                                print(f"[APPROVE] list_users fallback failed: {list_err}")
                                traceback.print_exc()

            if not supabase_user_id:
                # If we still failed to get or create a Supabase ID, restore status to pending so admin can retry
                print(f"[APPROVE] Failed to obtain Supabase ID for {p.email}. Reverting pending status to 'pending'.")
                p.status = "pending"
                await session.commit()
                return

            # 3. Create local User profile
            new_user = User(
                id=supabase_user_id,
                full_name=p.full_name,
                email=p.email,
                phone=p.phone,
                role=p.role,
                is_approved=True,
            )
            session.add(new_user)
            await session.flush()

            # 4. Enrollments / Assignments
            from app.db.models import Enrollment, Student, Batch
            if p.role == UserRole.student:
                student_profile = Student(
                    id=uuid.uuid4(),
                    user_id=new_user.id,
                    parent_id=new_user.id,
                    first_name=p.full_name.split()[0],
                    last_name=" ".join(p.full_name.split()[1:]) if len(p.full_name.split()) > 1 else "",
                )
                session.add(student_profile)
                await session.flush()
                
                if p.selected_batch_ids:
                    for b_id in p.selected_batch_ids:
                        enrollment = Enrollment(
                            id=uuid.uuid4(),
                            student_id=student_profile.id,
                            batch_id=b_id
                        )
                        session.add(enrollment)
                        
            elif p.role == UserRole.teacher:
                if p.selected_batch_ids:
                    for b_id in p.selected_batch_ids:
                        res = await session.execute(select(Batch).where(Batch.id == b_id))
                        batch = res.scalars().first()
                        if batch:
                            batch.teacher_id = new_user.id

            # 5. Welcome notification
            welcome_notif = Notification(
                id=uuid.uuid4(),
                user_id=new_user.id,
                title="Account Approved! 🎉",
                message=f"Hi {p.full_name}, welcome to BuddyBloom! You can now log in.",
                is_read=False,
            )
            session.add(welcome_notif)
            
            # Save push token for future use
            if p.push_token:
                from app.db.models import UserPushToken
                existing_token_res = await session.execute(
                    select(UserPushToken).where(UserPushToken.push_token == p.push_token)
                )
                existing_token = existing_token_res.scalars().first()
                if existing_token:
                    existing_token.user_id = new_user.id
                else:
                    new_push = UserPushToken(
                        id=uuid.uuid4(),
                        user_id=new_user.id,
                        push_token=p.push_token,
                        device_type="unknown"
                    )
                    session.add(new_push)
                await session.flush()

            # 6. Trigger real-time push notification for the newly approved user
            from app.services.notification_service import NotificationService
            await NotificationService.send_push_notification(
                session, 
                new_user.id, 
                "Account Approved! 🎉", 
                f"Hi {p.full_name}, welcome to BuddyBloom! You can now log in.",
                {"type": "approval"}
            )
            
            p.hashed_temp_password = "REDACTED"
            await session.commit()

    background_tasks.add_task(process_approval_task, str(pending.id))
    return {
        "message": "User approved. Registration is being completed in the background.",
        "pending_id": str(pending.id)
    }



@router.post("/reject/{pending_id}")
async def reject_registration(pending_id: str, body: RejectRequest, db: AsyncSession = Depends(get_db)):
    """
    Admin rejects a registration with an optional reason.
    The pending record is kept (status=rejected) so the admin has an audit trail.
    """
    pend_res = await db.execute(
        select(PendingRegistration).where(PendingRegistration.id == pending_id)
    )
    pending = pend_res.scalars().first()

    if not pending:
        raise HTTPException(status_code=404, detail="Pending registration not found.")
    if pending.status != "pending":
        raise HTTPException(status_code=409, detail=f"Registration is already {pending.status}.")

    pending.status = "rejected"
    pending.rejection_reason = body.reason
    pending.hashed_temp_password = "REDACTED"  # Clear the password
    await db.commit()

    return {"message": f"Registration for {pending.email} rejected."}


@router.get("/test-token")
async def get_test_token(email: str = "test@example.com"):
    """Generate a mock JWT token for local testing."""
    from jose import jwt as jose_jwt
    payload = {
        "sub": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
        "role": "authenticated",
        "email": email,
    }
    token = jose_jwt.encode(payload, settings.SUPABASE_JWT_SECRET, algorithm="HS256")
    return {"access_token": token, "token_type": "bearer"}
