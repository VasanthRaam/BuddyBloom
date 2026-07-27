"""
Authentication endpoints:
  POST /auth/register        — public, creates PendingRegistration + notifies admins
  POST /auth/login           — public, verifies Supabase + checks is_approved
  GET  /auth/pending         — admin only, list pending registrations
  POST /auth/approve/{id}    — admin only, creates Supabase Auth user + local User + deletes pending
  POST /auth/reject/{id}     — admin only, marks pending as rejected with optional reason
"""
from fastapi import APIRouter, HTTPException, Depends, status, BackgroundTasks
from pydantic import BaseModel, EmailStr
from supabase import create_client, Client
from app.core.config import settings
from app.db.database import get_db
from app.db.models import User, UserRole, PendingRegistration, Notification
from app.core.security import verify_token
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import uuid
import logging

logger = logging.getLogger("app.api.auth")

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
    mother_name: str | None = None
    father_name: str | None = None
    parent_phone_number: str | None = None
    dob: str | None = None
    education_qualification: str | None = None
    profile_picture: str | None = None

class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    selected_profile_id: str | None = None

class ApproveRequest(BaseModel):
    pass  # No body needed

class RejectRequest(BaseModel):
    reason: str | None = "No reason provided."

class GoogleSyncRequest(BaseModel):
    access_token: str
    email: EmailStr
    full_name: str
    selected_profile_id: str | None = None

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
    logger.info(f"[AUTH-REGISTER] Request received for email={request.email}, name={request.full_name}, role={request.role}")
    
    # Validate role — only teacher, student, parent can self-register
    allowed_roles = {"teacher", "student", "parent"}
    if request.role not in allowed_roles:
        logger.warning(f"[AUTH-REGISTER] Invalid role registration attempted: {request.role}")
        raise HTTPException(status_code=400, detail="Invalid role. Allowed: teacher, student, parent")

    # Check if email already has an ACTIVE pending registration (case-insensitive)
    from sqlalchemy import func
    existing_pending = await db.execute(
        select(PendingRegistration).where(
            func.lower(PendingRegistration.email) == func.lower(request.email),
            PendingRegistration.status == "pending"
        )
    )
    if existing_pending.scalars().first():
        logger.warning(f"[AUTH-REGISTER] Email {request.email} already has a pending registration request.")
        raise HTTPException(status_code=409, detail="A registration request for this email is already pending.")

    # Validate that selected course_ids exist in database
    if request.course_ids:
        from app.db.models import Course
        res_c = await db.execute(select(Course.id).where(Course.id.in_(request.course_ids)))
        found_courses = res_c.scalars().all()
        if len(found_courses) != len(request.course_ids):
            logger.warning(f"[AUTH-REGISTER] Invalid course selection: requested={request.course_ids}, found={found_courses}")
            raise HTTPException(status_code=400, detail="One or more selected courses are invalid.")
            
    # Validate that selected batch_ids exist in database
    if request.batch_ids:
        from app.db.models import Batch
        res_b = await db.execute(select(Batch.id).where(Batch.id.in_(request.batch_ids)))
        found_batches = res_b.scalars().all()
        if len(found_batches) != len(request.batch_ids):
            logger.warning(f"[AUTH-REGISTER] Invalid batch selection: requested={request.batch_ids}, found={found_batches}")
            raise HTTPException(status_code=400, detail="One or more selected batches are invalid.")

    # Delete any existing rejected/approved registration requests for this email to allow re-applying (case-insensitive)
    from sqlalchemy import delete
    await db.execute(
        delete(PendingRegistration).where(func.lower(PendingRegistration.email) == func.lower(request.email))
    )

    # Check if email already exists in the main users table (case-insensitive)
    existing_user = await db.execute(
        select(User).where(func.lower(User.email) == func.lower(request.email))
    )
    if existing_user.scalars().first():
        logger.warning(f"[AUTH-REGISTER] Email {request.email} is already registered in users table.")
        raise HTTPException(status_code=409, detail="This email is already registered. Please login.")

    # Parse Date of Birth securely to avoid DB casting errors
    import datetime
    parsed_dob = None
    if request.dob:
        try:
            parsed_dob = datetime.datetime.strptime(request.dob, "%Y-%m-%d").date()
        except ValueError as dob_err:
            logger.warning(f"[AUTH-REGISTER] DOB parsing failed for {request.dob}: {dob_err}. Falling back to null.")
            pass # fallback to null if invalid

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
        mother_name=request.mother_name,
        father_name=request.father_name,
        parent_phone_number=request.parent_phone_number,
        dob=parsed_dob,
        education_qualification=request.education_qualification,
        profile_picture=request.profile_picture,
    )
    db.add(pending)
    await db.flush()
    logger.info(f"[AUTH-REGISTER] Stored pending registration with ID={pending.id} for email={request.email}")

    # Trigger notifications in background
    async def notify_admins(pending_id_str, full_name, role_str):
        from app.db.database import AsyncSessionLocal
        from app.services.notification_service import NotificationService
        from app.db.models import User, UserRole, Notification
        import uuid
        try:
            logger.info(f"[AUTH-REGISTER-NOTIF] Starting admin notifications for pending_id: {pending_id_str}")
            async with AsyncSessionLocal() as session:
                admin_res = await session.execute(select(User).where(User.role == UserRole.admin))
                admins = admin_res.scalars().all()
                logger.info(f"[AUTH-REGISTER-NOTIF] Found {len(admins)} admin(s) to notify.")
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
                    try:
                        await NotificationService.send_push_notification(
                            session, admin.id, "New Registration Request 👤",
                            f"{full_name} ({role_str}) has requested to join. Tap to review.",
                            {"type": "registration", "id": pending_id_str}
                        )
                        logger.info(f"[AUTH-REGISTER-NOTIF] Sent push notification to admin {admin.email}")
                    except Exception as push_err:
                        logger.error(f"[AUTH-REGISTER-NOTIF] Push notification failed for admin {admin.email}: {push_err}", exc_info=True)
                await session.commit()
                logger.info(f"[AUTH-REGISTER-NOTIF] Completed admin notifications successfully.")
        except Exception as bg_exc:
            logger.error(f"[AUTH-REGISTER-NOTIF] Background notification task failed: {bg_exc}", exc_info=True)

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
    logger.info(f"[AUTH-LOGIN] Received login request for email={request.email}")
    from sqlalchemy import func
    
    # 0. Check if user is pending registration FIRST.
    pend_res = await db.execute(
        select(PendingRegistration).where(func.lower(PendingRegistration.email) == func.lower(request.email))
    )
    pending = pend_res.scalars().first()
    if pending:
        logger.info(f"[AUTH-LOGIN] Found pending registration record for email={request.email} with status={pending.status}")
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
    logger.info(f"[AUTH-LOGIN] Attempting Supabase sign-in for email={request.email}")
    try:
        response = supabase.auth.sign_in_with_password({
            "email": request.email,
            "password": request.password,
        })
        logger.info(f"[AUTH-LOGIN] Supabase sign-in successful for email={request.email}")
    except Exception as e:
        logger.warning(f"[AUTH-LOGIN] Supabase auth failed for email={request.email}: {e}")
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    supabase_id = response.user.id
    email = response.user.email

    # Convert string ID to UUID object to avoid DB type comparison issues
    try:
        supabase_uuid = uuid.UUID(str(supabase_id))
    except ValueError as uuid_err:
        logger.error(f"[AUTH-LOGIN] Failed to convert Supabase user.id={supabase_id} to UUID: {uuid_err}")
        supabase_uuid = None

    # 2. Fetch local profiles — try by Supabase ID first, then fall back to email
    logger.info(f"[AUTH-LOGIN] Resolving local user profile for email={email}, uuid={supabase_uuid}")
    approved_users = []
    if supabase_uuid:
        result = await db.execute(select(User).where(User.id == supabase_uuid))
        users_list = result.scalars().all()
        approved_users.extend([u for u in users_list if u.is_approved])

    result = await db.execute(
        select(User).where(func.lower(User.email) == func.lower(email))
    )
    users_by_email = result.scalars().all()
    for u in users_by_email:
        if u.is_approved and u not in approved_users:
            approved_users.append(u)

    logger.info(f"[AUTH-LOGIN] Found {len(approved_users)} approved profiles for {email}")

    # 3. Edge-case: the user exists in Supabase Auth but NOT in our DB
    if not approved_users:
        logger.warning(f"[AUTH-LOGIN] No approved local profile found for email={email} (but exists in Supabase)")
        # Check if they have a pending registration
        pend_res = await db.execute(
            select(PendingRegistration).where(func.lower(PendingRegistration.email) == func.lower(email))
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

    # 4. Handle multiple profiles if no specific profile is selected
    if len(approved_users) > 1 and not request.selected_profile_id:
        logger.info(f"[AUTH-LOGIN] Multiple approved profiles detected. Returning choices to client.")
        return {
            "type": "multiple_profiles",
            "profiles": [
                {
                    "id": str(u.id),
                    "full_name": u.full_name,
                    "email": u.email,
                    "role": _role_value(u.role)
                } for u in approved_users
            ]
        }

    # Resolve specific user
    if request.selected_profile_id:
        logger.info(f"[AUTH-LOGIN] Resolving user with selected profile ID={request.selected_profile_id}")
        db_user = next((u for u in approved_users if str(u.id) == request.selected_profile_id), None)
        if not db_user:
            logger.warning(f"[AUTH-LOGIN] Selected profile ID={request.selected_profile_id} was not found or is not approved.")
            raise HTTPException(status_code=404, detail="Selected profile not found or not approved.")
    else:
        db_user = approved_users[0]
        logger.info(f"[AUTH-LOGIN] Defaulting to first approved profile: ID={db_user.id}")

    user_data = {
        "id": str(db_user.id),
        "email": db_user.email,
        "role": _role_value(db_user.role),
        "full_name": db_user.full_name,
        "created_at": db_user.created_at.isoformat() if db_user.created_at else None,
    }

    logger.info(f"[AUTH-LOGIN] Login successful for user ID={db_user.id}, role={db_user.role}")
    return {
        "access_token": response.session.access_token,
        "refresh_token": response.session.refresh_token,
        "token_type": "bearer",
        "user": user_data,
    }

@router.post("/google-sync")
async def google_sync(request: GoogleSyncRequest, db: AsyncSession = Depends(get_db)):
    """
    Sync a Google-authenticated user with our local database.
    If the user doesn't exist, return 404 so the app can redirect to Register.
    """
    logger.info(f"[GOOGLE-SYNC] Sync request received for email={request.email}")
    from sqlalchemy import func
    
    # Verify the Supabase access token for security
    try:
        logger.info(f"[GOOGLE-SYNC] Verifying access token for email={request.email}...")
        token_payload = await verify_token(request.access_token)
        token_email = token_payload.get("email")
        if not token_email:
            logger.warning(f"[GOOGLE-SYNC] Token payload is missing email for {request.email}")
            raise HTTPException(status_code=401, detail="Token does not contain an email address.")
        if token_email.lower() != request.email.lower():
            logger.warning(f"[GOOGLE-SYNC] Token email mismatch: token={token_email.lower()} vs request={request.email.lower()}")
            raise HTTPException(status_code=401, detail="Token email does not match requested email.")
        logger.info(f"[GOOGLE-SYNC] Token verification succeeded for email={request.email}")
    except HTTPException:
        raise
    except Exception as token_err:
        logger.error(f"[GOOGLE-SYNC] Token verification error for email={request.email}: {token_err}", exc_info=True)
        raise HTTPException(status_code=401, detail=f"Invalid or expired credentials: {str(token_err)}")
    
    # 1. Fetch local profiles by email (case-insensitive)
    result = await db.execute(
        select(User).where(func.lower(User.email) == func.lower(request.email))
    )
    db_users = result.scalars().all()
    approved_users = [u for u in db_users if u.is_approved]
    logger.info(f"[GOOGLE-SYNC] Found {len(approved_users)} approved profiles for email={request.email}")

    if not approved_users:
        logger.info(f"[GOOGLE-SYNC] No approved profiles found. Checking pending registrations for email={request.email}")
        # Check if they have a pending registration
        pend_res = await db.execute(
            select(PendingRegistration).where(func.lower(PendingRegistration.email) == func.lower(request.email))
        )
        pending = pend_res.scalars().first()
        if pending:
            logger.info(f"[GOOGLE-SYNC] Found pending registration with status={pending.status}")
            if pending.status == "pending":
                raise HTTPException(status_code=403, detail="Your Google registration is pending admin approval.")
            if pending.status == "rejected":
                raise HTTPException(status_code=403, detail=f"Your registration was rejected. Reason: {pending.rejection_reason}")
        
        # Truly not found -> Trigger registration flow on mobile
        logger.info(f"[GOOGLE-SYNC] Profile not found. Returning 404 to trigger registration.")
        raise HTTPException(status_code=404, detail="Profile not found. Please complete registration.")

    # Handle multiple profiles if no specific profile is selected
    if len(approved_users) > 1 and not request.selected_profile_id:
        logger.info(f"[GOOGLE-SYNC] Multiple approved profiles detected. Returning choices to client.")
        return {
            "type": "multiple_profiles",
            "profiles": [
                {
                    "id": str(u.id),
                    "full_name": u.full_name,
                    "email": u.email,
                    "role": _role_value(u.role)
                } for u in approved_users
            ]
        }

    # Resolve specific user
    if request.selected_profile_id:
        logger.info(f"[GOOGLE-SYNC] Resolving selected profile ID={request.selected_profile_id}")
        db_user = next((u for u in approved_users if str(u.id) == request.selected_profile_id), None)
        if not db_user:
            logger.warning(f"[GOOGLE-SYNC] Selected profile ID={request.selected_profile_id} was not found or is not approved.")
            raise HTTPException(status_code=404, detail="Selected profile not found or not approved.")
    else:
        db_user = approved_users[0]
        logger.info(f"[GOOGLE-SYNC] Defaulting to first approved profile: ID={db_user.id}")

    logger.info(f"[GOOGLE-SYNC] Sync successful for user ID={db_user.id}, role={db_user.role}")
    return {
        "type": "login_success",
        "access_token": request.access_token,
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
    logger.info(f"[AUTH-APPROVE] Received approve request for pending_id: {pending_id}")
    pend_res = await db.execute(
        select(PendingRegistration).where(PendingRegistration.id == pending_id)
    )
    pending = pend_res.scalars().first()

    if not pending:
        logger.warning(f"[AUTH-APPROVE] Pending registration not found for ID: {pending_id}")
        raise HTTPException(status_code=404, detail="Pending registration not found.")
    if pending.status != "pending":
        logger.warning(f"[AUTH-APPROVE] Pending registration status is {pending.status}, expected pending.")
        raise HTTPException(status_code=409, detail=f"Registration is already {pending.status}.")

    # Guard: race condition — another admin already approved
    existing = await db.execute(select(User).where(User.email == pending.email))
    if existing.scalars().first():
        logger.warning(f"[AUTH-APPROVE] User with email={pending.email} already exists in users table. Redacting password.")
        pending.status = "approved"
        pending.hashed_temp_password = "REDACTED"
        await db.commit()
        raise HTTPException(status_code=409, detail="A user with this email is already registered.")

    # Synchronously mark as approved and commit, so UI is unblocked immediately
    pending.status = "approved"
    await db.commit()
    logger.info(f"[AUTH-APPROVE] Marked pending_id={pending_id} as approved in database. Scheduling background creation...")

    async def process_approval_task(p_id_str):
        from app.db.database import AsyncSessionLocal
        from app.db.models import PendingRegistration, User, UserRole, Notification
        from app.core.config import settings
        from supabase import create_client as _cc
        import uuid
        import traceback
        
        logger.info(f"[APPROVE-TASK] Starting background approval task for pending_id: {p_id_str}")
        
        async with AsyncSessionLocal() as session:
            try:
                # 1. Fetch pending record again inside background session
                p_res = await session.execute(
                    select(PendingRegistration).where(PendingRegistration.id == uuid.UUID(p_id_str))
                )
                p = p_res.scalars().first()
                if not p:
                    logger.error(f"[APPROVE-TASK] Pending registration record not found for ID: {p_id_str}")
                    return
                
                logger.info(f"[APPROVE-TASK] Processing approval for email={p.email}, role={p.role}")
                saved_password = p.hashed_temp_password
                
                # 2. Supabase Auth account creation
                supabase_user_id = None
                if saved_password == "GOOGLE_AUTH_PLACEHOLDER":
                    # For Google users, they already exist in Supabase Auth
                    # The pending ID is their Supabase User ID
                    supabase_user_id = p.id
                    logger.info(f"[APPROVE-TASK] Google user detected. Using pending ID as Supabase ID: {supabase_user_id}")
                else:
                    try:
                        sign_in_check = supabase.auth.sign_in_with_password({
                            "email": p.email,
                            "password": saved_password,
                        })
                        supabase_user_id = sign_in_check.user.id
                        supabase.auth.sign_out()
                        logger.info(f"[APPROVE-TASK] Existing user signed in successfully: {supabase_user_id}")
                    except Exception as e:
                        logger.info(f"[APPROVE-TASK] sign_in_with_password check (expected for new users): {e}")
                        
                    if not supabase_user_id:
                        try:
                            if settings.SUPABASE_SERVICE_KEY:
                                logger.info(f"[APPROVE-TASK] Initializing admin client for email: {p.email}...")
                                admin_client = _cc(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
                                auth_response = admin_client.auth.admin.create_user({
                                    "email": p.email,
                                    "password": saved_password,
                                    "email_confirm": True,
                                })
                                supabase_user_id = auth_response.user.id
                                logger.info(f"[APPROVE-TASK] Created Supabase user successfully: {supabase_user_id}")
                            else:
                                logger.info(f"[APPROVE-TASK] Service key not found, using signup for: {p.email}...")
                                auth_response = supabase.auth.sign_up({
                                    "email": p.email,
                                    "password": saved_password,
                                })
                                if auth_response.user:
                                    supabase_user_id = auth_response.user.id
                                    logger.info(f"[APPROVE-TASK] Signed up user successfully: {supabase_user_id}")
                        except Exception as e:
                            logger.error(f"[APPROVE-TASK] Supabase user creation failed: {e}", exc_info=True)
                            err = str(e)
                            if any(msg in err.lower() for msg in ["already exists", "already registered", "already been registered"]):
                                try:
                                    logger.info("[APPROVE-TASK] User already exists in Supabase. Listing users to find matching email...")
                                    admin_client_to_use = admin_client if 'admin_client' in locals() else supabase
                                    all_users_resp = admin_client_to_use.auth.admin.list_users()
                                    users_list = getattr(all_users_resp, 'users', all_users_resp)
                                    for u in users_list:
                                        u_email = getattr(u, 'email', None) or (isinstance(u, dict) and u.get('email'))
                                        if u_email and u_email.lower() == p.email.lower():
                                            supabase_user_id = getattr(u, 'id', None) or (isinstance(u, dict) and u.get('id'))
                                            logger.info(f"[APPROVE-TASK] Found existing user ID: {supabase_user_id}")
                                            break
                                except Exception as list_err:
                                    logger.error(f"[APPROVE-TASK] list_users fallback failed: {list_err}", exc_info=True)

                if not supabase_user_id:
                    logger.error(f"[APPROVE-TASK] Failed to obtain Supabase ID for {p.email}. Reverting pending status to 'pending'.")
                    p.status = "pending"
                    await session.commit()
                    return

                # 3. Create local User profile
                logger.info(f"[APPROVE-TASK] Creating local User profile with ID: {supabase_user_id}")
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

                # 4. Enrollments / Assignments
                from app.db.models import Enrollment, Student, Batch
                if p.role == UserRole.student:
                    logger.info(f"[APPROVE-TASK] Creating student profile for User ID: {new_user.id}")
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
                    
                    if p.selected_batch_ids:
                        logger.info(f"[APPROVE-TASK] Creating student enrollments for batches: {p.selected_batch_ids}")
                        for b_id in p.selected_batch_ids:
                            enrollment = Enrollment(
                                id=uuid.uuid4(),
                                student_id=student_profile.id,
                                batch_id=b_id
                            )
                            session.add(enrollment)
                            
                elif p.role == UserRole.teacher:
                    if p.selected_batch_ids:
                        logger.info(f"[APPROVE-TASK] Assigning teacher to batches: {p.selected_batch_ids}")
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
                    logger.info(f"[APPROVE-TASK] Saving push token: {p.push_token}")
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
                try:
                    logger.info(f"[APPROVE-TASK] Triggering push notification for User ID: {new_user.id}")
                    await NotificationService.send_push_notification(
                        session, 
                        new_user.id, 
                        "Account Approved! 🎉", 
                        f"Hi {p.full_name}, welcome to BuddyBloom! You can now log in.",
                        {"type": "approval"}
                    )
                except Exception as push_err:
                    logger.error(f"[APPROVE-TASK] Push notification sending failed: {push_err}", exc_info=True)
                p.hashed_temp_password = "REDACTED"
                await session.commit()
                logger.info(f"[APPROVE-TASK] Background approval completed successfully for email: {p.email}")
            except Exception as task_exc:
                logger.error(f"[APPROVE-TASK] Database transaction failed for pending_id {p_id_str}: {task_exc}", exc_info=True)
                await session.rollback()
                try:
                    revert_res = await session.execute(
                        select(PendingRegistration).where(PendingRegistration.id == uuid.UUID(p_id_str))
                    )
                    revert_p = revert_res.scalars().first()
                    if revert_p:
                        logger.info(f"[APPROVE-TASK] Reverting pending registration status for {revert_p.email} back to 'pending'.")
                        revert_p.status = "pending"
                        await session.commit()
                except Exception as rollback_err:
                    logger.error(f"[APPROVE-TASK] Failed to revert pending registration status: {rollback_err}", exc_info=True)

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
    logger.info(f"[AUTH-REJECT] Received reject request for pending_id: {pending_id}, reason: {body.reason}")
    pend_res = await db.execute(
        select(PendingRegistration).where(PendingRegistration.id == pending_id)
    )
    pending = pend_res.scalars().first()

    if not pending:
        logger.warning(f"[AUTH-REJECT] Pending registration not found for ID: {pending_id}")
        raise HTTPException(status_code=404, detail="Pending registration not found.")
    if pending.status != "pending":
        logger.warning(f"[AUTH-REJECT] Pending registration status is {pending.status}, expected pending.")
        raise HTTPException(status_code=409, detail=f"Registration is already {pending.status}.")

    pending.status = "rejected"
    pending.rejection_reason = body.reason
    pending.hashed_temp_password = "REDACTED"  # Clear the password
    await db.commit()
    logger.info(f"[AUTH-REJECT] Registration for {pending.email} successfully rejected.")

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


class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    email: EmailStr
    otp: str
    new_password: str

@router.post("/forgot-password")
async def forgot_password(request: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    """
    Generate a 6-digit OTP for password reset.
    Since there is no email service configured, the OTP is returned in the response for testing.
    """
    from sqlalchemy import func
    from app.db.models import PasswordResetOTP
    from datetime import datetime, timedelta, timezone
    import random
    
    # 1. Check if user exists
    user_res = await db.execute(
        select(User).where(func.lower(User.email) == func.lower(request.email))
    )
    db_user = user_res.scalars().first()
    
    if not db_user:
        # We don't want to leak whether an email exists for security reasons,
        # but for this specific app's requirements, a 404 is helpful to the user.
        raise HTTPException(status_code=404, detail="Email not found in our records.")
        
    # 2. Invalidate previous OTPs
    await db.execute(
        PasswordResetOTP.__table__.update()
        .where(PasswordResetOTP.email == request.email)
        .where(PasswordResetOTP.is_used == False)
        .values(is_used=True)
    )
    
    # 3. Generate new 6-digit OTP
    otp_code = str(random.randint(100000, 999999))
    expires = datetime.now(timezone.utc) + timedelta(minutes=15)
    
    new_otp = PasswordResetOTP(
        email=request.email,
        otp=otp_code,
        expires_at=expires,
        is_used=False
    )
    db.add(new_otp)
    await db.commit()
    
    # 4. Send Email using the SMTP service
    from app.services.email_service import EmailService
    import asyncio
    
    # We can send the email in the background to not block the response
    asyncio.create_task(asyncio.to_thread(EmailService.send_otp_email, request.email, otp_code))
    
    print(f"[AUTH] FORGOT PASSWORD OTP generated for {request.email}")
    
    return {
        "message": "Reset code generated successfully. Please check your email.",
    }

@router.post("/reset-password")
async def reset_password(request: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    """
    Verify the OTP and force-update the user's password using Supabase Admin API.
    """
    from sqlalchemy import func
    from app.db.models import PasswordResetOTP
    from datetime import datetime, timezone
    from supabase import create_client as _cc
    
    # 1. Verify OTP
    otp_res = await db.execute(
        select(PasswordResetOTP)
        .where(func.lower(PasswordResetOTP.email) == func.lower(request.email))
        .where(PasswordResetOTP.otp == request.otp)
        .where(PasswordResetOTP.is_used == False)
    )
    otp_record = otp_res.scalars().first()
    
    if not otp_record:
        raise HTTPException(status_code=400, detail="Invalid reset code.")
        
    if otp_record.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Reset code has expired. Please request a new one.")
        
    # 2. Fetch the local user to get their Supabase ID
    user_res = await db.execute(
        select(User).where(func.lower(User.email) == func.lower(request.email))
    )
    db_user = user_res.scalars().first()
    
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found.")
        
    # 3. Update password in Supabase via Admin API
    if not settings.SUPABASE_SERVICE_KEY:
        raise HTTPException(status_code=500, detail="Supabase Service Key is not configured. Cannot update password.")
        
    admin_client = _cc(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
    try:
        admin_client.auth.admin.update_user_by_id(str(db_user.id), {"password": request.new_password})
    except Exception as e:
        print(f"[RESET PASSWORD] Supabase Error: {e}")
        # Could fail if the user is a Google-only user without an email/password identity setup.
        raise HTTPException(status_code=400, detail="Could not update password. Ensure you registered with email/password.")
        
    # 4. Mark OTP as used
    otp_record.is_used = True
    await db.commit()
    
    return {"message": "Password has been successfully reset. You can now log in."}


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    """
    Authenticated endpoint: change the logged-in user's own password.

    Requires:
      - current_password  — verified against Supabase (prevents unauthorized changes)
      - new_password      — min 6 characters

    Only works for email/password users. Google-only users will get a 400.
    """
    from sqlalchemy import func
    from supabase import create_client as _cc

    user_id_str = current_user.get("sub") or current_user.get("id")
    if not user_id_str:
        raise HTTPException(status_code=401, detail="Invalid token.")

    if len(request.new_password) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters.")

    if request.current_password == request.new_password:
        raise HTTPException(status_code=400, detail="New password must be different from the current password.")

    # 1. Fetch the user's email from DB
    user_res = await db.execute(
        select(User).where(User.id == user_id_str)
    )
    db_user = user_res.scalars().first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found.")

    # 2. Verify the current password by attempting a Supabase sign-in
    try:
        supabase.auth.sign_in_with_password({
            "email": db_user.email,
            "password": request.current_password,
        })
        supabase.auth.sign_out()
    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Current password is incorrect."
        )

    # 3. Update the password via Supabase Admin API
    if not settings.SUPABASE_SERVICE_KEY:
        raise HTTPException(status_code=500, detail="Service key not configured.")

    admin_client = _cc(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
    try:
        admin_client.auth.admin.update_user_by_id(str(db_user.id), {"password": request.new_password})
    except Exception as e:
        logger.error(f"[CHANGE-PASSWORD] Supabase update failed for user {db_user.id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=400,
            detail="Could not update password. This account may use Google sign-in instead of email/password."
        )

    logger.info(f"[CHANGE-PASSWORD] Password changed for user {db_user.id} ({db_user.email})")
    return {"message": "Password updated successfully."}



class MobileLoginInitRequest(BaseModel):
    phone: str

class MobileLoginVerifyRequest(BaseModel):

    phone: str
    otp: str
    selected_profile_id: str | None = None

@router.post("/mobile-login-init")
async def mobile_login_init(request: MobileLoginInitRequest, db: AsyncSession = Depends(get_db)):
    logger.info(f"[MOBILE-LOGIN-INIT] Request received for phone: {request.phone}")
    from sqlalchemy import func
    from app.db.models import MobileLoginOTP
    from datetime import datetime, timedelta, timezone
    import random
    from app.services.sms_service import SMSService

    # 1. Check if ANY user with this phone exists and is approved (robust matching)
    phone_clean = request.phone.strip()
    phone_digits = "".join(c for c in phone_clean if c.isdigit())
    last_10 = phone_digits[-10:] if len(phone_digits) >= 10 else phone_digits
    
    if len(last_10) == 10:
        logger.info(f"[MOBILE-LOGIN-INIT] Looking up phone with suffix: {last_10}")
        user_res = await db.execute(
            select(User).where(
                (User.phone == phone_clean) |
                (User.phone.like(f"%{last_10}"))
            )
        )
    else:
        user_res = await db.execute(
            select(User).where(User.phone == phone_clean)
        )
        
    db_users = user_res.scalars().all()
    logger.info(f"[MOBILE-LOGIN-INIT] Found {len(db_users)} profiles matching phone number {phone_clean}")

    if not db_users:
        logger.warning(f"[MOBILE-LOGIN-INIT] Phone number {request.phone} not registered in local database.")
        raise HTTPException(status_code=404, detail="Phone number not registered.")
        
    approved_users = [u for u in db_users if u.is_approved]
    if not approved_users:
        logger.warning(f"[MOBILE-LOGIN-INIT] Found matching profiles but none are approved yet.")
        raise HTTPException(status_code=403, detail="Account pending approval.")

    # 2. Invalidate previous OTPs
    await db.execute(
        MobileLoginOTP.__table__.update()
        .where(MobileLoginOTP.phone == request.phone)
        .where(MobileLoginOTP.is_used == False)
        .values(is_used=True)
    )
    
    # 3. Generate new 6-digit OTP
    otp_code = str(random.randint(100000, 999999))
    expires = datetime.now(timezone.utc) + timedelta(minutes=5)
    
    new_otp = MobileLoginOTP(
        phone=request.phone,
        otp=otp_code,
        expires_at=expires,
        is_used=False
    )
    db.add(new_otp)
    await db.commit()
    
    # 4. Send SMS (Mocked via console)
    SMSService.send_otp(request.phone, otp_code)
    
    return {
        "message": "OTP sent successfully.",
    }

@router.post("/mobile-login-verify")
async def mobile_login_verify(request: MobileLoginVerifyRequest, db: AsyncSession = Depends(get_db)):
    logger.info(f"[MOBILE-LOGIN-VERIFY] Request received for phone: {request.phone}, OTP: {request.otp}")
    from app.db.models import MobileLoginOTP
    from datetime import datetime, timezone, timedelta
    from jose import jwt as jose_jwt
    
    # 1. Verify OTP
    # Check phone exactly or suffix matching in the OTP record
    phone_clean = request.phone.strip()
    phone_digits = "".join(c for c in phone_clean if c.isdigit())
    last_10 = phone_digits[-10:] if len(phone_digits) >= 10 else phone_digits
    
    if len(last_10) == 10:
        otp_res = await db.execute(
            select(MobileLoginOTP)
            .where(
                ((MobileLoginOTP.phone == phone_clean) | (MobileLoginOTP.phone.like(f"%{last_10}"))) &
                (MobileLoginOTP.otp == request.otp) &
                (MobileLoginOTP.is_used == False)
            )
        )
    else:
        otp_res = await db.execute(
            select(MobileLoginOTP)
            .where(MobileLoginOTP.phone == phone_clean)
            .where(MobileLoginOTP.otp == request.otp)
            .where(MobileLoginOTP.is_used == False)
        )
        
    otp_record = otp_res.scalars().first()
    
    if not otp_record:
        logger.warning(f"[MOBILE-LOGIN-VERIFY] Invalid OTP attempt for phone: {request.phone}")
        raise HTTPException(status_code=400, detail="Invalid OTP.")
        
    if otp_record.expires_at < datetime.now(timezone.utc):
        logger.warning(f"[MOBILE-LOGIN-VERIFY] Expired OTP attempt for phone: {request.phone}")
        raise HTTPException(status_code=400, detail="OTP has expired. Please request a new one.")
        
    # 2. Fetch the users (robust matching)
    if len(last_10) == 10:
        user_res = await db.execute(
            select(User).where(
                (User.phone == phone_clean) |
                (User.phone.like(f"%{last_10}"))
            )
        )
    else:
        user_res = await db.execute(
            select(User).where(User.phone == phone_clean)
        )
        
    db_users = user_res.scalars().all()
    approved_users = [u for u in db_users if u.is_approved]
    logger.info(f"[MOBILE-LOGIN-VERIFY] Verified OTP. Found {len(approved_users)} approved profiles.")
    
    if not approved_users:
        logger.warning(f"[MOBILE-LOGIN-VERIFY] No approved profiles found for phone: {request.phone}")
        raise HTTPException(status_code=404, detail="No approved user found for this phone number.")
        
    # 3. Handle multiple profiles if no specific profile is selected
    if len(approved_users) > 1 and not request.selected_profile_id:
        logger.info(f"[MOBILE-LOGIN-VERIFY] Multiple profiles detected. Returning selection list.")
        return {
            "type": "multiple_profiles",
            "profiles": [
                {
                    "id": str(u.id),
                    "full_name": u.full_name,
                    "email": u.email,
                    "role": _role_value(u.role)
                } for u in approved_users
            ]
        }
        
    # 4. Resolve the specific user to log in
    if request.selected_profile_id:
        db_user = next((u for u in approved_users if str(u.id) == request.selected_profile_id), None)
        if not db_user:
            logger.warning(f"[MOBILE-LOGIN-VERIFY] Selected profile ID={request.selected_profile_id} not found/approved.")
            raise HTTPException(status_code=404, detail="Selected profile not found or not approved.")
    else:
        db_user = approved_users[0]
        logger.info(f"[MOBILE-LOGIN-VERIFY] Resolved user to first profile: {db_user.id}")
        
    # 5. Generate custom JWT
    payload = {
        "sub": str(db_user.id),
        "role": _role_value(db_user.role),
        "email": db_user.email,
        "exp": datetime.now(timezone.utc) + timedelta(days=365) # 365 days expiration
    }
    token = jose_jwt.encode(payload, settings.SUPABASE_JWT_SECRET, algorithm="HS256")
    
    # 6. Mark OTP as used
    otp_record.is_used = True
    await db.commit()
    logger.info(f"[MOBILE-LOGIN-VERIFY] Custom JWT generated successfully for user ID={db_user.id}")
    
    user_data = {
        "id": str(db_user.id),
        "email": db_user.email,
        "role": _role_value(db_user.role),
        "full_name": db_user.full_name,
        "created_at": db_user.created_at.isoformat() if db_user.created_at else None,
    }
    
    return {
        "type": "login_success",
        "access_token": token,
        "token_type": "bearer",
        "user": user_data,
    }

# --- Firebase OTP Login Integration ---

class FirebaseLoginVerifyRequest(BaseModel):
    id_token: str
    selected_profile_id: str | None = None

async def verify_firebase_token(id_token: str, project_id: str) -> str:
    import httpx
    from jose import jwt as jose_jwt
    
    url = "https://www.googleapis.com/robot/v1/metadata/x509/securetoken@system.gserviceaccount.com"
    async with httpx.AsyncClient() as client:
        res = await client.get(url)
        if res.status_code != 200:
            raise HTTPException(status_code=500, detail="Failed to fetch Google public keys.")
        public_keys = res.json()

    try:
        unverified_header = jose_jwt.get_unverified_header(id_token)
        kid = unverified_header.get("kid")
        if not kid or kid not in public_keys:
            raise HTTPException(status_code=400, detail="Invalid token header (kid not found or invalid).")

        public_key_pem = public_keys[kid]
        
        claims = jose_jwt.decode(
            id_token,
            public_key_pem,
            algorithms=["RS256"],
            options={"verify_aud": False, "verify_iss": False}
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid Firebase token: {str(e)}")

    phone_number = claims.get("phone_number")
    if not phone_number:
        raise HTTPException(status_code=400, detail="Firebase token does not contain a verified phone number.")

    return phone_number

@router.post("/firebase-login-verify")
async def firebase_login_verify(request: FirebaseLoginVerifyRequest, db: AsyncSession = Depends(get_db)):
    logger.info(f"[FIREBASE-LOGIN-VERIFY] Request received")
    from app.db.models import User
    from jose import jwt as jose_jwt
    from datetime import datetime, timezone, timedelta
    
    firebase_project_id = settings.FIREBASE_PROJECT_ID or "buddybloom-app"
    try:
        phone = await verify_firebase_token(request.id_token, firebase_project_id)
        logger.info(f"[FIREBASE-LOGIN-VERIFY] Firebase token verified. Phone={phone}")
    except Exception as token_err:
        logger.error(f"[FIREBASE-LOGIN-VERIFY] Firebase token verification failed: {token_err}", exc_info=True)
        raise HTTPException(status_code=401, detail=f"Firebase token verification failed: {str(token_err)}")
        
    phone_clean = phone.strip()
    phone_digits = "".join(c for c in phone_clean if c.isdigit())
    last_10 = phone_digits[-10:] if len(phone_digits) >= 10 else phone_digits
    
    if len(last_10) == 10:
        logger.info(f"[FIREBASE-LOGIN-VERIFY] Querying profiles with phone suffix: {last_10}")
        user_res = await db.execute(
            select(User).where(
                (User.phone == phone_clean) |
                (User.phone.like(f"%{last_10}"))
            )
        )
    else:
        user_res = await db.execute(
            select(User).where(User.phone == phone_clean)
        )
    db_users = user_res.scalars().all()
    logger.info(f"[FIREBASE-LOGIN-VERIFY] Found {len(db_users)} profiles matching phone {phone_clean}")
        
    if not db_users:
        logger.warning(f"[FIREBASE-LOGIN-VERIFY] Phone number {phone} is not registered in local database.")
        raise HTTPException(status_code=404, detail="Phone number not registered.")
        
    approved_users = [u for u in db_users if u.is_approved]
    if not approved_users:
        logger.warning(f"[FIREBASE-LOGIN-VERIFY] Matching profiles exist but none are approved.")
        raise HTTPException(status_code=403, detail="Account pending approval.")
        
    if len(approved_users) > 1 and not request.selected_profile_id:
        logger.info(f"[FIREBASE-LOGIN-VERIFY] Multiple profiles found. Returning options.")
        return {
            "type": "multiple_profiles",
            "profiles": [
                {
                    "id": str(u.id),
                    "full_name": u.full_name,
                    "email": u.email,
                    "role": _role_value(u.role)
                } for u in approved_users
            ]
        }
        
    if request.selected_profile_id:
        db_user = next((u for u in approved_users if str(u.id) == request.selected_profile_id), None)
        if not db_user:
            logger.warning(f"[FIREBASE-LOGIN-VERIFY] Selected profile ID={request.selected_profile_id} not found/approved.")
            raise HTTPException(status_code=404, detail="Selected profile not found or not approved.")
    else:
        db_user = approved_users[0]
        logger.info(f"[FIREBASE-LOGIN-VERIFY] Resolved user to first profile: {db_user.id}")
        
    payload = {
        "sub": str(db_user.id),
        "role": _role_value(db_user.role),
        "email": db_user.email,
        "exp": datetime.now(timezone.utc) + timedelta(days=365)
    }
    token = jose_jwt.encode(payload, settings.SUPABASE_JWT_SECRET, algorithm="HS256")
    logger.info(f"[FIREBASE-LOGIN-VERIFY] Custom JWT generated successfully for user ID={db_user.id}")
    
    user_data = {
        "id": str(db_user.id),
        "email": db_user.email,
        "role": _role_value(db_user.role),
        "full_name": db_user.full_name,
        "created_at": db_user.created_at.isoformat() if db_user.created_at else None,
    }
    
    return {
        "type": "login_success",
        "access_token": token,
        "token_type": "bearer",
        "user": user_data,
    }
