from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case, cast, Float
from app.db.database import get_db
from app.db.models import User, Student, FeePayment, QuizAttempt, Homework, Batch
from app.schemas.dashboard import DashboardStatsResponse, AdminStats, TeacherStats, StudentStats
from app.api.deps import get_current_user

router = APIRouter()

@router.get("/stats", response_model=DashboardStatsResponse)
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    role = current_user["role"]
    user_id = current_user["id"]
    
    response = DashboardStatsResponse()

    if role == "admin":
        # Revenue
        rev_res = await db.execute(select(func.sum(FeePayment.amount)).where(FeePayment.status == "paid"))
        revenue = rev_res.scalar() or 0.0
        
        pend_res = await db.execute(select(func.sum(FeePayment.amount)).where(FeePayment.status == "pending"))
        pending = pend_res.scalar() or 0.0
        
        stud_count = await db.execute(select(func.count(User.id)).where(User.role == "student"))
        teach_count = await db.execute(select(func.count(User.id)).where(User.role == "teacher"))
        
        response.admin = AdminStats(
            total_revenue=revenue,
            pending_fees=pending,
            total_students=stud_count.scalar() or 0,
            total_teachers=teach_count.scalar() or 0
        )
        
    elif role == "teacher":
        from app.db.models import Quiz
        
        # Avg performance (quiz attempts for quizzes created by this teacher)
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
        
        batches = await db.execute(select(func.count(Batch.id)).where(Batch.teacher_id == user_id))
        hw_pend = await db.execute(select(func.count(Homework.id)).where(Homework.teacher_id == user_id))
        
        response.teacher = TeacherStats(
            avg_performance=round(avg_perf * 100, 1),
            active_batches=batches.scalar() or 0,
            pending_homeworks=hw_pend.scalar() or 0
        )
        
    elif role == "student":
        from app.db.models import Attendance, AttendanceStatus
        # Individual stats
        st_res = await db.execute(select(Student).where(Student.user_id == user_id))
        student = st_res.scalars().first()
        
        if student:
            # Quiz Stats
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
            avg_score, count = perf_res.first() or (0, 0)
            
            # Attendance Stats
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
                attendance_rate=round(attendance_rate, 1),
                avg_quiz_score=round(float(avg_score or 0) * 100, 1),
                completed_quizzes=count or 0
            )

    elif role == "parent":
        from app.db.models import Attendance, AttendanceStatus
        # Find students linked to this parent
        res_studs = await db.execute(select(Student).where(Student.parent_id == user_id))
        students = res_studs.scalars().all()
        
        if students:
            student_ids = [s.id for s in students]
            
            # Aggregated Quiz Stats
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
            avg_score, count = perf_res.first() or (0, 0)
            
            # Aggregated Attendance Stats
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
                attendance_rate=round(attendance_rate, 1),
                avg_quiz_score=round(float(avg_score or 0) * 100, 1),
                completed_quizzes=count or 0
            )

    return response
