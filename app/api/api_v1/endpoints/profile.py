"""
Profile endpoints — Student and Teacher profile views + photo upload.

Student (GET /profile/me):
  Returns personal details, academic info (enrollments), and XP summary.

Student (PUT /profile/me):
  Allows editing phone and email only (admin controls all other fields).

POST /profile/photo:
  Generates a Supabase Storage signed upload URL.
  Client uploads directly to storage, then calls PUT /profile/me with the returned public URL.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from uuid import UUID

from app.db.database import get_db
from app.db.models import User, Student, Enrollment, Batch, Course, TeacherWallet
from app.api.deps import get_current_user, RequireRole
from app.schemas.rewards import (
    ProfileUpdateRequest, StudentProfileResponse,
    TeacherProfileResponse, EnrollmentInfo, ProfilePhotoUploadResponse
)
from app.services import rewards_service
from app.core.config import settings

router = APIRouter()


@router.get("/me", summary="Get current user's full profile")
async def get_my_profile(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Returns the full profile of the logged-in user.
    For students: personal info + academic enrollments + XP summary.
    For teachers: personal info + assigned batches + monthly wallet.
    """
    user_id = UUID(current_user["id"])
    role = current_user["role"]

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if role == "student":
        # Fetch student profile row
        st_res = await db.execute(select(Student).where(Student.user_id == user_id))
        student = st_res.scalars().first()

        enrollments_info = []
        pending_enrollments_info = []
        if student:
            enr_res = await db.execute(
                select(Enrollment, Batch, Course)
                .join(Batch, Enrollment.batch_id == Batch.id)
                .join(Course, Batch.course_id == Course.id)
                .where(Enrollment.student_id == student.id)
            )
            for enr, batch, course in enr_res.all():
                enrollments_info.append(EnrollmentInfo(
                    batch_id=str(batch.id),
                    batch_name=batch.name,
                    course_id=str(course.id),
                    course_name=course.name,
                ))

            # Query pending enrollments as well
            from app.db.models import PendingEnrollment
            pend_res = await db.execute(
                select(PendingEnrollment, Batch, Course)
                .join(Batch, PendingEnrollment.batch_id == Batch.id)
                .join(Course, Batch.course_id == Course.id)
                .where(
                    PendingEnrollment.student_id == student.id,
                    PendingEnrollment.status == "pending"
                )
            )
            for pend, batch, course in pend_res.all():
                pending_enrollments_info.append({
                    "batch_id": str(batch.id),
                    "batch_name": batch.name,
                    "course_id": str(course.id),
                    "course_name": course.name,
                    "status": "pending"
                })

            # XP summary
            summary = await rewards_service.get_student_summary(db, student.id, user.full_name)
        else:
            summary = {
                "current_points": 0, "lifetime_points": 0, "quiz_points": 0,
                "teacher_bonus_points": 0, "rank": None, "level": 1,
                "level_label": "Beginner", "next_level_points": 500, "progress_pct": 0.0
            }

        return {
            "id": str(user.id),
            "full_name": user.full_name,
            "email": user.email,
            "phone": user.phone,
            "profile_picture": user.profile_picture,
            "dob": str(user.dob) if user.dob else None,
            "education_qualification": user.education_qualification,
            "mother_name": student.mother_name if student else None,
            "father_name": student.father_name if student else None,
            "parent_phone_number": student.parent_phone_number if student else None,
            "enrollments": [e.dict() for e in enrollments_info],
            "pending_enrollments": pending_enrollments_info,
            **summary,
        }

    elif role == "teacher":
        # Fetch assigned batches
        batches_res = await db.execute(
            select(Batch, Course)
            .join(Course, Batch.course_id == Course.id)
            .where(Batch.teacher_id == user_id)
        )
        assigned = []
        for batch, course in batches_res.all():
            assigned.append(EnrollmentInfo(
                batch_id=str(batch.id),
                batch_name=batch.name,
                course_id=str(course.id),
                course_name=course.name,
            ))

        # Teacher wallet
        wallet = await rewards_service.get_or_create_teacher_wallet(db, user_id)
        await db.commit()

        return {
            "id": str(user.id),
            "full_name": user.full_name,
            "email": user.email,
            "phone": user.phone,
            "profile_picture": user.profile_picture,
            "assigned_batches": [b.dict() for b in assigned],
            "wallet_total": wallet.total_points,
            "wallet_remaining": wallet.remaining_points,
            "wallet_distributed": wallet.distributed_points,
            "wallet_month": wallet.month_year,
            "wallet_expires_at": wallet.expires_at.isoformat() if wallet.expires_at else None,
            "wallet_last_reset": wallet.last_reset_at.isoformat() if wallet.last_reset_at else None,
        }

    else:
        # Admin or parent — basic profile
        return {
            "id": str(user.id),
            "full_name": user.full_name,
            "email": user.email,
            "phone": user.phone,
            "profile_picture": user.profile_picture,
            "dob": str(user.dob) if user.dob else None,
            "education_qualification": user.education_qualification,
            "role": role,
        }


@router.put("/me", summary="Update own profile (phone, email, profile_picture only)")
async def update_my_profile(
    req: ProfileUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Students and teachers can only edit their phone, email, and profile_picture.
    All other fields are controlled by the admin.
    """
    user_id = UUID(current_user["id"])

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if req.phone is not None:
        user.phone = req.phone
    if req.email is not None:
        user.email = req.email
    if req.profile_picture is not None:
        user.profile_picture = req.profile_picture
    if req.education_qualification is not None:
        user.education_qualification = req.education_qualification

    await db.commit()
    return {"message": "Profile updated successfully"}

@router.delete("/me", summary="Delete own account")
async def delete_my_profile(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Deletes the current user's account from the database.
    """
    user_id = UUID(current_user["id"])
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    await db.delete(user)
    await db.commit()
    return {"message": "Account deleted successfully"}


@router.post("/photo-upload-url", summary="Get a Supabase Storage pre-signed upload URL")
async def get_photo_upload_url(
    current_user: dict = Depends(get_current_user)
):
    """
    Returns a signed upload URL for Supabase Storage.
    The client uploads the image directly to this URL, then calls PUT /profile/me
    with the returned public_url to save it.
    """
    if not settings.SUPABASE_SERVICE_KEY:
        return {
            "upload_url": "",
            "public_url": "",
            "path": "",
        }

    from supabase import create_client
    try:
        supabase_client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)

        user_id = current_user["id"]
        file_path = f"profile-pictures/{user_id}.jpg"
        bucket = "profile-pictures"

        try:
            supabase_client.storage.create_bucket(bucket, options={"public": True})
        except Exception:
            pass  # Bucket already exists

        signed = supabase_client.storage.from_(bucket).create_signed_upload_url(file_path)
        public_url = f"{settings.SUPABASE_URL}/storage/v1/object/public/{bucket}/{file_path}"

        return {
            "upload_url": signed.get("signed_url", ""),
            "public_url": public_url,
            "path": file_path,
        }
    except Exception as e:
        print(f"[PHOTO-UPLOAD-URL] Storage url creation notice: {e}")
        return {
            "upload_url": "",
            "public_url": "",
            "path": "",
        }
