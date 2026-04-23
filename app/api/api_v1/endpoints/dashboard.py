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
        # Avg performance (quiz attempts)
        perf_res = await db.execute(
            select(
                func.avg(
                    case(
                        (QuizAttempt.max_score > 0, cast(QuizAttempt.total_score, Float) / QuizAttempt.max_score),
                        else_=0
                    )
                )
            )
        )
        avg_perf = perf_res.scalar() or 0.0
        
        batches = await db.execute(select(func.count(Batch.id)))
        hw_pend = await db.execute(select(func.count(Homework.id))) # Simplified for now
        
        response.teacher = TeacherStats(
            avg_performance=round(avg_perf * 100, 1),
            active_batches=batches.scalar() or 0,
            pending_homeworks=hw_pend.scalar() or 0
        )
        
    elif role == "student":
        # Individual stats
        # Need to find student record
        st_res = await db.execute(select(Student).where(Student.user_id == user_id))
        student = st_res.scalars().first()
        
        if student:
            perf_res = await db.execute(select(func.avg(QuizAttempt.total_score), func.count(QuizAttempt.id)).where(QuizAttempt.student_id == student.id))
            avg_score, count = perf_res.first() or (0, 0)
            
            response.student = StudentStats(
                attendance_rate=95.0, # Placeholder
                avg_quiz_score=float(avg_score or 0),
                completed_quizzes=count or 0
            )

    return response
