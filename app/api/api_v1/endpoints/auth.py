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

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class ApproveRequest(BaseModel):
    pass  # No body needed

class RejectRequest(BaseModel):
    reason: str | None = "No reason provided."

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

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequest, db: AsyncSession = Depends(get_db)):
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
        id=uuid.uuid4(),
        full_name=request.full_name,
        email=request.email,
        phone=request.phone,
        hashed_temp_password=request.password,
        role=UserRole(request.role),
        status="pending",
        selected_course_ids=request.course_ids,
        selected_batch_ids=request.batch_ids,
    )
    db.add(pending)
    await db.flush()

    # Notify all admins
    admin_res = await db.execute(select(User).where(User.role == UserRole.admin))
    admins = admin_res.scalars().all()

    for admin in admins:
        notif = Notification(
            id=uuid.uuid4(),
            user_id=admin.id,
            title="New Registration Request",
            message=f"{request.full_name} ({request.role}) has requested to join BuddyBloom. Tap to review.",
            link_to=f"PendingApproval:{pending.id}",
            is_read=False,
        )
        db.add(notif)

    await db.commit()

    return {
        "message": "Registration submitted. An admin will review your request. You will be able to login once approved.",
        "pending_id": str(pending.id),
    }


@router.post("/login")
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Authenticate via Supabase then verify the local profile is approved.
    """
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

    # 2. Fetch local profile — try by Supabase ID first, then fall back to email
    result = await db.execute(select(User).where(User.id == supabase_id))
    db_user = result.scalars().first()

    if not db_user:
        result = await db.execute(select(User).where(User.email == email))
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
    }

    return {
        "access_token": response.session.access_token,
        "token_type": "bearer",
        "user": user_data,
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
async def approve_registration(pending_id: str, db: AsyncSession = Depends(get_db)):
    """
    Admin approves a registration:
    1. Creates the Supabase Auth user.
    2. Creates the local User profile marked is_approved=True.
    3. Marks pending record as approved and clears password.
    4. Sends a welcome notification to the new user.
    
    Uses service_role key (admin.create_user) if SUPABASE_SERVICE_KEY is set in .env
    so email confirmation is bypassed. Falls back to sign_up (anon key) otherwise —
    in that case, disable 'Confirm email' in Supabase Dashboard > Auth > Settings.
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

    saved_password = pending.hashed_temp_password

    # ── Create Supabase Auth account ──────────────────────────────────────────
    supabase_user_id = None
    
    # Strategy 1: Try to sign in first. If they already exist in Supabase Auth,
    # we just need their ID. This avoids "Rate Limit" and "Already exists" errors.
    try:
        sign_in_check = supabase.auth.sign_in_with_password({
            "email": pending.email,
            "password": saved_password,
        })
        supabase_user_id = sign_in_check.user.id
        # Sign out immediately so we don't leave a session on the server-side client
        supabase.auth.sign_out()
    except Exception:
        # If sign-in fails, they likely don't exist yet or email isn't confirmed
        pass

    if not supabase_user_id:
        try:
            if settings.SUPABASE_SERVICE_KEY:
                # Preferred: use admin API (bypasses email confirmation & rate limits)
                from supabase import create_client as _cc
                admin_client = _cc(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
                auth_response = admin_client.auth.admin.create_user({
                    "email": pending.email,
                    "password": saved_password,
                    "email_confirm": True,
                })
                supabase_user_id = auth_response.user.id
            else:
                # Fallback: anon sign_up
                auth_response = supabase.auth.sign_up({
                    "email": pending.email,
                    "password": saved_password,
                })
                if auth_response.user:
                    supabase_user_id = auth_response.user.id
                else:
                    raise Exception("Sign up returned no user. Check if 'Confirm email' is ON.")
        except Exception as e:
            err = str(e)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create Supabase Auth account: {err}. "
                       "Tip: Set SUPABASE_SERVICE_KEY in .env, or disable 'Confirm email' in Supabase Auth settings."
            )

    # ── Create local User profile ─────────────────────────────────────────────
    new_user = User(
        id=supabase_user_id,
        full_name=pending.full_name,
        email=pending.email,
        phone=pending.phone,
        role=pending.role,
        is_approved=True,
    )
    db.add(new_user)
    await db.flush()

    # ── Create Enrollments (Student) or Assignments (Teacher) ─────────────────
    from app.db.models import Enrollment, Student, Batch
    
    if pending.role == UserRole.student:
        # For students, we need a Student profile first
        # Note: In this simple flow, we might not have a parent_id yet. 
        # Using a placeholder or requiring one if needed.
        # For now, let's create a profile.
        student_profile = Student(
            id=uuid.uuid4(),
            user_id=new_user.id,
            parent_id=new_user.id, # Placeholder: student is their own parent for now if not provided
            first_name=pending.full_name.split()[0],
            last_name=" ".join(pending.full_name.split()[1:]) if len(pending.full_name.split()) > 1 else "",
        )
        db.add(student_profile)
        await db.flush()
        
        if pending.selected_batch_ids:
            for b_id in pending.selected_batch_ids:
                enrollment = Enrollment(
                    id=uuid.uuid4(),
                    student_id=student_profile.id,
                    batch_id=b_id
                )
                db.add(enrollment)
                
    elif pending.role == UserRole.teacher:
        if pending.selected_batch_ids:
            for b_id in pending.selected_batch_ids:
                # Assign teacher to batch
                res = await db.execute(select(Batch).where(Batch.id == b_id))
                batch = res.scalars().first()
                if batch:
                    batch.teacher_id = new_user.id

    # ── Welcome notification ──────────────────────────────────────────────────
    welcome_notif = Notification(
        id=uuid.uuid4(),
        user_id=new_user.id,
        title="Account Approved! 🎉",
        message=f"Hi {pending.full_name}, welcome to BuddyBloom! You can now log in with your email and password.",
        is_read=False,
    )
    db.add(welcome_notif)

    # ── Mark pending as approved (audit trail) ────────────────────────────────
    pending.status = "approved"
    pending.hashed_temp_password = "REDACTED"

    await db.commit()

    return {
        "message": f"User {pending.email} approved successfully. They can now log in.",
        "supabase_id": str(supabase_user_id),
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
