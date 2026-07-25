from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case, cast, Float
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
    role = (current_user.get("role") or "").lower()
    raw_user_id = current_user.get("id")
    
    try:
        user_id = uuid.UUID(str(raw_user_id)) if raw_user_id else None
    except Exception:
        user_id = raw_user_id

    response = DashboardStatsResponse()

    try:
        if role == "admin":
            # Revenue & Pending
            rev_res = await db.execute(select(func.sum(FeePayment.amount)).where(FeePayment.status == "paid"))
            revenue = rev_res.scalar() or 0.0

            pend_res = await db.execute(select(func.sum(FeePayment.amount)).where(FeePayment.status == "pending"))
            pending = pend_res.scalar() or 0.0

            # Count Students and Teachers safely matching Enum or String
            stud_count = await db.execute(
                select(func.count(User.id)).where(User.role.in_([UserRole.student, "student", "STUDENT"]))
            )
            teach_count = await db.execute(
                select(func.count(User.id)).where(User.role.in_([UserRole.teacher, "teacher", "TEACHER"]))
            )

            response.admin = AdminStats(
                total_revenue=float(revenue or 0.0),
                pending_fees=float(pending or 0.0),
                total_students=stud_count.scalar() or 0,
                total_teachers=teach_count.scalar() or 0
            )

        elif role == "teacher":
            from app.db.models import Quiz

            avg_perf = 0.0
            if user_id:
                perf_res = await db.execute(
                    select(
                        func.avg(
                            case(
                                (QuizAttempt.max_score > 0, cast(QuizAttempt.total_score, Float) / QuizAttempt.max_score),
                                else_=0
                            )
                        )
                    ).join(Quiz, Quiz.id == QuizAttempt.quiz_id).where((Quiz.created_by == user_id) | (Quiz.created_by == str(raw_user_id)))
                )
                avg_perf = perf_res.scalar() or 0.0

            batches_count = 0
            hw_count = 0
            if user_id:
                b_res = await db.execute(select(func.count(Batch.id)).where((Batch.teacher_id == user_id) | (Batch.teacher_id == str(raw_user_id))))
                batches_count = b_res.scalar() or 0

                hw_res = await db.execute(select(func.count(Homework.id)).where((Homework.teacher_id == user_id) | (Homework.teacher_id == str(raw_user_id))))
                hw_count = hw_res.scalar() or 0

            response.teacher = TeacherStats(
                avg_performance=round(float(avg_perf or 0.0) * 100, 1),
                active_batches=batches_count,
                pending_homeworks=hw_count
            )

        elif role == "student":
            from app.db.models import Attendance, AttendanceStatus

            student = None
            if user_id:
                st_res = await db.execute(select(Student).where((Student.user_id == user_id) | (Student.id == user_id)))
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

                total_att = await db.execute(select(func.count(Attendance.id)).where(Attendance.student_id == student.id))
                present_att = await db.execute(
                    select(func.count(Attendance.id))
                    .where(
                        Attendance.student_id == student.id,
                        Attendance.status.in_([AttendanceStatus.present, 'present', 'Present', 'PRESENT'])
                    )
                )
                total_count = total_att.scalar() or 0
                present_count = present_att.scalar() or 0
                attendance_rate = (present_count / total_count * 100) if total_count > 0 else 0.0

                response.student = StudentStats(
                    attendance_rate=round(float(attendance_rate or 0.0), 1),
                    avg_quiz_score=round(float(avg_score or 0.0) * 100, 1),
                    completed_quizzes=count or 0
                )
            else:
                response.student = StudentStats(
                    attendance_rate=0.0,
                    avg_quiz_score=0.0,
                    completed_quizzes=0
                )

        elif role == "parent":
            from app.db.models import Attendance, AttendanceStatus

            students = []
            if user_id:
                res_studs = await db.execute(select(Student).where((Student.parent_id == user_id) | (Student.parent_id == str(raw_user_id))))
                students = res_studs.scalars().all()

            if students:
                student_ids = [s.id for s in students]

                perf_res = await db.execute(
                    select(
                        func.avg(
                            case(
                                (QuizAttempt.max_score > 0, cast(QuizAttempt.total_score, Float) / QuizAttempt.max_score),
                                else_=0
                            )
                        ),
                        func.count(QuizAttempt.id)
                    ).where(QuizAttempt.student_id.in_(student_ids))
                )
                row = perf_res.first()
                avg_score = row[0] if row else 0
                count = row[1] if row else 0

                total_att = await db.execute(select(func.count(Attendance.id)).where(Attendance.student_id.in_(student_ids)))
                present_att = await db.execute(
                    select(func.count(Attendance.id))
                    .where(
                        Attendance.student_id.in_(student_ids),
                        Attendance.status.in_([AttendanceStatus.present, 'present', 'Present', 'PRESENT'])
                    )
                )
                total_count = total_att.scalar() or 0
                present_count = present_att.scalar() or 0
                attendance_rate = (present_count / total_count * 100) if total_count > 0 else 0.0

                response.student = StudentStats(
                    attendance_rate=round(float(attendance_rate or 0.0), 1),
                    avg_quiz_score=round(float(avg_score or 0.0) * 100, 1),
                    completed_quizzes=count or 0
                )
            else:
                response.student = StudentStats(
                    attendance_rate=0.0,
                    avg_quiz_score=0.0,
                    completed_quizzes=0
                )

    except Exception as e:
        logger.error(f"[DASHBOARD-STATS] Failed to compute stats for user_id={raw_user_id}, role={role}: {e}", exc_info=True)

    return response
