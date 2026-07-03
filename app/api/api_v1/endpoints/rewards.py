"""
XP Rewards endpoints.

GET  /rewards/summary           — Student's full points summary (balance, level, rank)
GET  /rewards/history           — Paginated list of point transactions
GET  /rewards/leaderboard       — All students ranked, filterable by course/batch/period
GET  /rewards/catalog           — Available reward items (for all authenticated users)
POST /rewards/redeem/{reward_id} — Student redeems a reward
GET  /rewards/teacher/wallet    — Teacher's current monthly wallet
POST /rewards/teacher/give      — Teacher gives points to a student
POST /rewards/admin/reset-wallets  — Admin manually triggers wallet reset
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, text
from typing import Optional
from uuid import UUID
import uuid

from app.db.database import get_db
from app.db.models import (
    User, Student, Enrollment, Batch, Course,
    PointTransaction, RewardCatalog, RewardRedemption
)
from app.api.deps import get_current_user, RequireRole
from app.schemas.rewards import (
    TeacherGivePointsRequest, RedeemRequest, LeaderboardEntry, PointTransactionOut
)
from app.services import rewards_service

router = APIRouter()


@router.get("/summary", summary="Student's XP points summary")
async def get_points_summary(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Returns current balance, lifetime points, level, rank for the logged-in student."""
    if current_user["role"] not in ("student",):
        raise HTTPException(status_code=403, detail="Only students have an XP wallet.")

    user_id = UUID(current_user["id"])
    st_res = await db.execute(select(Student).where(Student.user_id == user_id))
    student = st_res.scalars().first()
    if not student:
        raise HTTPException(status_code=404, detail="Student profile not found.")

    return await rewards_service.get_student_summary(db, student.id, current_user["full_name"])


@router.get("/history", summary="Paginated point transaction history for logged-in student")
async def get_points_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    user_id = UUID(current_user["id"])
    st_res = await db.execute(select(Student).where(Student.user_id == user_id))
    student = st_res.scalars().first()
    if not student:
        raise HTTPException(status_code=404, detail="Student profile not found.")

    offset = (page - 1) * page_size

    count_res = await db.execute(
        select(func.count(PointTransaction.id))
        .where(PointTransaction.student_id == student.id)
    )
    total = count_res.scalar() or 0

    txn_res = await db.execute(
        select(PointTransaction, User)
        .outerjoin(User, PointTransaction.given_by == User.id)
        .where(PointTransaction.student_id == student.id)
        .order_by(PointTransaction.created_at.desc())
        .limit(page_size).offset(offset)
    )
    rows = txn_res.all()

    transactions = []
    for txn, giver in rows:
        transactions.append({
            "id": str(txn.id),
            "points": txn.points,
            "source": txn.source,
            "reason": txn.reason,
            "created_at": txn.created_at.isoformat(),
            "given_by_name": giver.full_name if giver else None,
        })

    return {
        "transactions": transactions,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/leaderboard", summary="Students leaderboard ranked by XP points")
async def get_leaderboard(
    course_id: Optional[str] = Query(None),
    batch_id: Optional[str] = Query(None),
    period: Optional[str] = Query(None, description="'monthly' or 'all' (default: all)"),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Returns a ranked leaderboard of students by XP points.
    Filterable by course, batch, monthly period, and searchable by name.
    """
    offset = (page - 1) * page_size

    # Build filters for time period
    period_filter = ""
    if period == "monthly":
        period_filter = "AND pt.created_at >= date_trunc('month', now())"

    # Search filter (safe — no string injection, use ILIKE with param)
    search_filter = ""
    search_param = None
    if search and search.strip():
        search_filter = "AND u.full_name ILIKE :search_val"
        search_param = f"%{search.strip()}%"

    # Build optional enrollment join + filter
    enrollment_join = ""
    enrollment_filter = ""
    extra_cols = "NULL::TEXT AS course_name, NULL::TEXT AS batch_name"
    if course_id or batch_id:
        enrollment_join = """
            JOIN enrollments enr ON enr.student_id = s.id
            JOIN batches b ON b.id = enr.batch_id
            JOIN courses c ON c.id = b.course_id
        """
        extra_cols = "MAX(c.name) AS course_name, MAX(b.name) AS batch_name"
        if course_id:
            enrollment_filter += f" AND c.id = '{course_id}'"
        if batch_id:
            enrollment_filter += f" AND b.id = '{batch_id}'"

    sql = text(f"""
        WITH base AS (
            SELECT
                s.id AS student_id,
                u.full_name,
                u.profile_picture,
                COALESCE(SUM(pt.points), 0) AS current_points,
                {extra_cols}
            FROM students s
            JOIN users u ON u.id = s.user_id
            LEFT JOIN point_transactions pt ON pt.student_id = s.id {period_filter}
            {enrollment_join}
            WHERE s.user_id IS NOT NULL
            {enrollment_filter}
            {search_filter}
            GROUP BY s.id, u.full_name, u.profile_picture
        ),
        ranked AS (
            SELECT *, RANK() OVER (ORDER BY current_points DESC) AS rank
            FROM base
        )
        SELECT * FROM ranked
        ORDER BY rank
        LIMIT :limit OFFSET :offset
    """)

    count_sql = text(f"""
        SELECT COUNT(DISTINCT s.id)
        FROM students s
        JOIN users u ON u.id = s.user_id
        {enrollment_join}
        WHERE s.user_id IS NOT NULL
        {enrollment_filter}
        {search_filter}
    """)

    params = {"limit": page_size, "offset": offset}
    if search_param:
        params["search_val"] = search_param

    result = await db.execute(sql, params)
    rows = result.fetchall()

    count_result = await db.execute(count_sql, {"search_val": search_param} if search_param else {})
    total = count_result.scalar() or 0

    entries = []
    for row in rows:
        entries.append({
            "rank": row.rank,
            "student_id": str(row.student_id),
            "student_name": row.full_name,
            "profile_picture": row.profile_picture,
            "course_name": row.course_name,
            "batch_name": row.batch_name,
            "current_points": row.current_points,
        })

    return {
        "entries": entries,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/catalog", summary="Get all active reward catalog items")
async def get_reward_catalog(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Returns all active reward items sorted by points required."""
    res = await db.execute(
        select(RewardCatalog)
        .where(RewardCatalog.is_active == True)
        .order_by(RewardCatalog.sort_order, RewardCatalog.points_required)
    )
    items = res.scalars().all()

    # Get student's current balance for unlocked state
    student_balance = 0
    if current_user["role"] == "student":
        st_res = await db.execute(
            select(Student).where(Student.user_id == UUID(current_user["id"]))
        )
        student = st_res.scalars().first()
        if student:
            student_balance = await rewards_service.get_student_balance(db, student.id)

    return {
        "items": [
            {
                "id": str(item.id),
                "title": item.title,
                "description": item.description,
                "points_required": item.points_required,
                "image_url": item.image_url,
                "is_active": item.is_active,
                "sort_order": item.sort_order,
                "is_unlocked": student_balance >= item.points_required,
                "points_needed": max(0, item.points_required - student_balance),
            }
            for item in items
        ],
        "student_balance": student_balance,
    }


@router.post("/redeem/{reward_id}", summary="Student redeems a reward with their XP points")
async def redeem_reward(
    reward_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(RequireRole(["student"]))
):
    """Redeems a reward. Points are immediately deducted and a redemption request is created."""
    user_id = UUID(current_user["id"])
    st_res = await db.execute(select(Student).where(Student.user_id == user_id))
    student = st_res.scalars().first()
    if not student:
        raise HTTPException(status_code=404, detail="Student profile not found.")

    redemption = await rewards_service.redeem_reward(db, student.id, UUID(reward_id))
    await db.commit()

    # Fetch reward title for response
    r_res = await db.execute(select(RewardCatalog).where(RewardCatalog.id == UUID(reward_id)))
    reward = r_res.scalars().first()

    return {
        "id": str(redemption.id),
        "reward_title": reward.title if reward else "",
        "points_spent": redemption.points_spent,
        "status": redemption.status,
        "redeemed_at": redemption.redeemed_at.isoformat(),
    }


@router.get("/teacher/wallet", summary="Get teacher's current monthly XP wallet")
async def get_teacher_wallet(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(RequireRole(["teacher", "admin"]))
):
    """Returns the teacher's monthly wallet info: remaining pts, distributed pts, expiry."""
    teacher_id = UUID(current_user["id"])
    wallet = await rewards_service.get_or_create_teacher_wallet(db, teacher_id)
    await db.commit()
    return {
        "total_points": wallet.total_points,
        "remaining_points": wallet.remaining_points,
        "distributed_points": wallet.distributed_points,
        "month_year": wallet.month_year,
        "expires_at": wallet.expires_at.isoformat() if wallet.expires_at else None,
        "last_reset_at": wallet.last_reset_at.isoformat() if wallet.last_reset_at else None,
    }


@router.post("/teacher/give", summary="Teacher gives XP points to a student")
async def give_points_to_student(
    req: TeacherGivePointsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(RequireRole(["teacher", "admin"]))
):
    """
    Teacher distributes points from their monthly wallet to a student.
    Deducts from wallet immediately. Fails if balance is insufficient.
    """
    teacher_id = UUID(current_user["id"])
    student_id = UUID(req.student_id)

    # Validate student exists
    st_res = await db.execute(select(Student).where(Student.id == student_id))
    student = st_res.scalars().first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")

    txn = await rewards_service.teacher_give_points(db, teacher_id, student_id, req.points, req.reason)
    await db.commit()

    return {
        "message": f"Successfully awarded {req.points} XP points.",
        "transaction_id": str(txn.id),
        "points": txn.points,
    }


@router.get("/teacher/students", summary="Get students list for teacher to award points to")
async def get_students_for_teacher(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(RequireRole(["teacher", "admin"]))
):
    """Returns list of students in the teacher's batches for the reward modal."""
    teacher_id = UUID(current_user["id"])

    if current_user["role"] == "teacher":
        # Only students in teacher's batches
        result = await db.execute(
            select(Student, User)
            .join(User, Student.user_id == User.id)
            .join(Enrollment, Enrollment.student_id == Student.id)
            .join(Batch, Batch.id == Enrollment.batch_id)
            .where(Batch.teacher_id == teacher_id)
            .distinct()
        )
    else:
        # Admin can see all students
        result = await db.execute(
            select(Student, User)
            .join(User, Student.user_id == User.id)
        )

    students = []
    for student, user in result.all():
        balance = await rewards_service.get_student_balance(db, student.id)
        students.append({
            "id": str(student.id),
            "name": user.full_name,
            "email": user.email,
            "profile_picture": user.profile_picture,
            "current_points": balance,
        })

    return {"students": students}


@router.post("/admin/reset-wallets", summary="Admin: Reset all teacher wallets for the new month")
async def admin_reset_wallets(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(RequireRole(["admin"]))
):
    """Manually triggers the monthly wallet reset for all teachers."""
    await rewards_service.reset_all_teacher_wallets(db)
    return {"message": "All teacher wallets have been reset to 1000 points."}


@router.post("/admin/catalog", summary="Admin: Add a new reward to the catalog")
async def add_reward_catalog_item(
    title: str,
    points_required: int,
    description: Optional[str] = None,
    image_url: Optional[str] = None,
    sort_order: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(RequireRole(["admin"]))
):
    """Adds a new reward item to the XP catalog."""
    from typing import Optional as Opt
    item = RewardCatalog(
        id=uuid.uuid4(),
        title=title,
        description=description,
        points_required=points_required,
        image_url=image_url,
        sort_order=sort_order,
    )
    db.add(item)
    await db.commit()
    return {"id": str(item.id), "message": "Reward added successfully."}


@router.get("/student/{student_id}/summary", summary="Admin/Teacher: Get a specific student's XP summary")
async def get_student_summary_by_id(
    student_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Returns XP summary for a specific student (admin/teacher view)."""
    st_res = await db.execute(
        select(Student, User)
        .join(User, Student.user_id == User.id)
        .where(Student.id == UUID(student_id))
    )
    row = st_res.first()
    if not row:
        raise HTTPException(status_code=404, detail="Student not found.")
    student, user = row
    return await rewards_service.get_student_summary(db, student.id, user.full_name)
