from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from uuid import UUID

from app.db.models import Student, Attendance, ProgressTracking, QuizAttempt, Quiz, Course, Question
from app.schemas.parent_dashboard import (
    AttendanceSummary, ProgressSummary, QuizResultSummary
)

class ParentDashboardService:
    @staticmethod
    async def verify_parent_access(db: AsyncSession, parent_id: UUID, student_id: UUID) -> bool:
        """Verify that the student_id belongs to the parent_id."""
        query = select(Student).where(
            Student.id == student_id,
            Student.parent_id == parent_id
        )
        result = await db.execute(query)
        return result.scalars().first() is not None

    @staticmethod
    async def get_students(db: AsyncSession, parent_id: UUID) -> list[Student]:
        query = select(Student).where(Student.parent_id == parent_id)
        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def get_attendance_summary(db: AsyncSession, student_id: UUID) -> AttendanceSummary:
        # Get counts
        count_query = select(
            Attendance.status,
            func.count(Attendance.id).label('count')
        ).where(
            Attendance.student_id == student_id
        ).group_by(Attendance.status)
        
        count_result = await db.execute(count_query)
        # Using .value because it's an Enum
        counts = {row.status.value: row.count for row in count_result}
        
        # Get individual records
        record_query = select(Attendance).where(Attendance.student_id == student_id).order_by(Attendance.date.desc())
        record_result = await db.execute(record_query)
        records = record_result.scalars().all()
        
        total_present = counts.get('present', 0)
        total_absent = counts.get('absent', 0)
        total_late = counts.get('late', 0)
        total_excused = counts.get('excused', 0)
        
        total_days = sum(counts.values())
        attendance_percentage = 0.0
        if total_days > 0:
            attendance_percentage = ((total_present + total_late) / total_days) * 100.0
            
        formatted_records = [
            {"date": r.date, "status": r.status.value} for r in records
        ]

        return AttendanceSummary(
            student_id=student_id,
            total_present=total_present,
            total_absent=total_absent,
            total_late=total_late,
            total_excused=total_excused,
            attendance_percentage=round(attendance_percentage, 2),
            records=formatted_records
        )

    @staticmethod
    async def get_progress_summary(db: AsyncSession, student_id: UUID) -> list[ProgressSummary]:
        query = select(
            ProgressTracking,
            Course.name.label("course_name")
        ).join(
            Course, ProgressTracking.course_id == Course.id
        ).where(
            ProgressTracking.student_id == student_id
        ).order_by(ProgressTracking.recorded_date.desc())
        
        result = await db.execute(query)
        
        summaries = []
        for progress, course_name in result:
            summaries.append(ProgressSummary(
                id=progress.id,
                course_name=course_name,
                milestone_name=progress.milestone_name,
                evaluation_score=progress.evaluation_score,
                remarks=progress.remarks,
                recorded_date=progress.recorded_date
            ))
        return summaries

    @staticmethod
    async def get_quiz_results(db: AsyncSession, student_id: UUID) -> list[QuizResultSummary]:
        # We need to join QuizAttempt, Quiz, and calculate max points from Question
        # For simplicity, we can fetch Attempts and Quizzes, then sum points.
        query = select(
            QuizAttempt,
            Quiz.title.label("quiz_title"),
            Course.name.label("course_name")
        ).join(
            Quiz, QuizAttempt.quiz_id == Quiz.id
        ).join(
            Course, Quiz.course_id == Course.id
        ).where(
            QuizAttempt.student_id == student_id
        ).order_by(QuizAttempt.attempted_at.desc())
        
        result = await db.execute(query)
        attempts_data = result.all()
        
        # Now fetch max scores for the quizzes
        quiz_ids = [attempt_data.QuizAttempt.quiz_id for attempt_data in attempts_data]
        max_scores_query = select(
            Question.quiz_id,
            func.sum(Question.points).label("max_score")
        ).where(
            Question.quiz_id.in_(quiz_ids)
        ).group_by(Question.quiz_id)
        
        max_scores_result = await db.execute(max_scores_query)
        max_scores = {row.quiz_id: row.max_score or 0 for row in max_scores_result}
        
        summaries = []
        for attempt, quiz_title, course_name in attempts_data:
            max_score = max_scores.get(attempt.quiz_id, 0)
            percentage = 0.0
            if max_score > 0:
                percentage = (attempt.total_score / max_score) * 100.0
                
            summaries.append(QuizResultSummary(
                attempt_id=attempt.id,
                quiz_title=quiz_title,
                course_name=course_name,
                total_score=attempt.total_score,
                max_score=max_score,
                attempted_at=attempt.attempted_at,
                percentage=round(percentage, 2)
            ))
            
        return summaries
