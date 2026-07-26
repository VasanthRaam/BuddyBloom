from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case, cast, Float, or_
import uuid
import logging
from app.db.database import get_db
from app.db.models import User, UserRole, Student, FeePayment, QuizAttempt, Homework, Batch
from app.schemas.dashboard import DashboardStatsResponse, AdminStats, TeacherStats, StudentStats
from app.api.deps import get_current_user

logger = logging.getLogger("app.api.dashboard")

router = APIRouter()

@router.get("/stats", response_model=DashboardStatsResponse)
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    raw_role = str(current_user.get("role") or "").lower()
    raw_user_id = current_user.get("id")

    try:
        user_id = uuid.UUID(str(raw_user_id)) if raw_user_id else None
    except Exception:
        user_id = None

    response = DashboardStatsResponse()

    is_admin = "admin" in raw_role
    is_teacher = "teacher" in raw_role
    is_student = "student" in raw_role
    is_parent = "parent" in raw_role

    # ── 1. ADMIN STATS ────────────────────────────────────────────────────────
    if is_admin:
        try:
            from app.db.models import Income

            # Revenue: paid fee payments (case-insensitive)
            rev_fees_res = await db.execute(
                select(func.sum(FeePayment.amount)).where(
                    or_(
                        FeePayment.status.ilike("paid"),
                    )
                )
            )
            rev_fees = rev_fees_res.scalar() or 0.0

            # Revenue: manual incomes
            rev_inc_res = await db.execute(select(func.sum(Income.amount)))
            rev_incomes = rev_inc_res.scalar() or 0.0

            total_rev = float(rev_fees) + float(rev_incomes)

            # Pending/unpaid fees (case-insensitive)
            pend_res = await db.execute(
                select(func.sum(FeePayment.amount)).where(
                    or_(
                        FeePayment.status.ilike("pending"),
                        FeePayment.status.ilike("unpaid"),
                        FeePayment.status.ilike("due"),
                        FeePayment.status.ilike("overdue"),
                    )
                )
            )
            pending = pend_res.scalar() or 0.0

            # Count Students from Student profile table
            st_count_res = await db.execute(select(func.count(Student.id)))
            total_studs = st_count_res.scalar() or 0

            # Count Teachers
            teach_count_res = await db.execute(
                select(func.count(User.id)).where(User.role == UserRole.teacher)
            )
            total_teachers = teach_count_res.scalar() or 0

            response.admin = AdminStats(
                total_revenue=float(total_rev),
                pending_fees=float(pending),
                total_students=int(total_studs),
                total_teachers=int(total_teachers)
            )
            logger.info(f"[DASHBOARD-STATS] Admin stats computed: revenue={total_rev}, students={total_studs}, teachers={total_teachers}")
        except Exception as e:
            logger.error(f"[DASHBOARD-STATS] Admin stats failed for user_id={raw_user_id}: {e}", exc_info=True)

    # ── 2. TEACHER STATS ──────────────────────────────────────────────────────
    if is_teacher or is_admin:
        try:
            from app.db.models import Quiz

            avg_perf = 0.0
            batches_count = 0
            hw_count = 0

            if user_id:
                perf_res = await db.execute(
                    select(
                        func.avg(
                            case(
                                (QuizAttempt.max_score > 0, cast(QuizAttempt.total_score, Float) / QuizAttempt.max_score),
                                else_=0
                            )
                        )
                    ).join(Quiz, Quiz.id == QuizAttempt.quiz_id).where(Quiz.created_by == user_id)
                )
                avg_perf = perf_res.scalar() or 0.0

                b_res = await db.execute(
                    select(func.count(Batch.id)).where(Batch.teacher_id == user_id)
                )
                batches_count = b_res.scalar() or 0

                hw_res = await db.execute(
                    select(func.count(Homework.id)).where(Homework.teacher_id == user_id)
                )
                hw_count = hw_res.scalar() or 0

            response.teacher = TeacherStats(
                avg_performance=round(float(avg_perf or 0.0) * 100, 1),
                active_batches=int(batches_count),
                pending_homeworks=int(hw_count)
            )
        except Exception as e:
            logger.error(f"[DASHBOARD-STATS] Teacher stats failed for user_id={raw_user_id}: {e}", exc_info=True)

    # ── 3. STUDENT / PARENT STATS ─────────────────────────────────────────────
    if is_student or is_parent:
        try:
            from app.db.models import Attendance, AttendanceStatus

            student = None
            if user_id:
                st_res = await db.execute(
                    select(Student).where(
                        or_(Student.user_id == user_id, Student.id == user_id)
                    )
                )
                student = st_res.scalars().first()

            if student:
                perf_res = await db.execute(
                    select(
                        func.avg(
                            case(
                                (QuizAttempt.max_score > 0, cast(QuizAttempt.total_score, Float) / QuizAttempt.max_score),
                                else_=0
                            )
                        ),
                        func.count(QuizAttempt.id)
                    ).where(QuizAttempt.student_id == student.id)
                )
                row = perf_res.first()
                avg_score = row[0] if row else 0
                count = row[1] if row else 0

                total_att = await db.execute(
                    select(func.count(Attendance.id)).where(Attendance.student_id == student.id)
                )
                present_att = await db.execute(
                    select(func.count(Attendance.id)).where(
                        Attendance.student_id == student.id,
                        Attendance.status == AttendanceStatus.present
                    )
                )
                total_count = total_att.scalar() or 0
                present_count = present_att.scalar() or 0
                attendance_rate = (present_count / total_count * 100) if total_count > 0 else 100.0

                response.student = StudentStats(
                    attendance_rate=round(float(attendance_rate or 0.0), 1),
                    avg_quiz_score=round(float(avg_score or 0.0) * 100, 1),
                    completed_quizzes=int(count or 0)
                )
            else:
                response.student = StudentStats(
                    attendance_rate=100.0,
                    avg_quiz_score=0.0,
                    completed_quizzes=0
                )
        except Exception as e:
            logger.error(f"[DASHBOARD-STATS] Student/parent stats failed for user_id={raw_user_id}: {e}", exc_info=True)

    return response
