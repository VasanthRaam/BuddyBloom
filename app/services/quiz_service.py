from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import or_
from uuid import UUID
from datetime import datetime

from app.db.models import Quiz, Question, Option, QuizAttempt, QuizAttemptAnswer, Batch, Course, Enrollment, Student, UserRole
from app.schemas.quiz import QuizCreate, QuestionCreate, QuizSubmission
from app.services.notification_service import NotificationService

class QuizService:
    @staticmethod
    async def get_quizzes(db: AsyncSession, user_id: UUID, role: str) -> list[Quiz]:
        base_query = select(Quiz).options(
            selectinload(Quiz.questions).selectinload(Question.options)
        )
        
        if role == UserRole.admin:
            query = base_query
        elif role == UserRole.teacher:
            # Quizzes created by teacher OR for courses they teach
            teacher_courses = select(Batch.course_id).where(Batch.teacher_id == user_id)
            query = base_query.where(
                or_(
                    Quiz.created_by == user_id,
                    Quiz.course_id.in_(teacher_courses)
                )
            )
        elif role == UserRole.student:
            # Quizzes for courses the student is enrolled in
            student_courses = (
                select(Batch.course_id)
                .join(Enrollment)
                .join(Student)
                .where(Student.user_id == user_id)
            )
            query = base_query.where(Quiz.course_id.in_(student_courses))
        elif role == UserRole.parent:
            # Quizzes for courses their children are enrolled in
            parent_courses = (
                select(Batch.course_id)
                .join(Enrollment)
                .join(Student)
                .where(Student.parent_id == user_id)
            )
            query = base_query.where(Quiz.course_id.in_(parent_courses))
        else:
            return []
            
        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def create_quiz(db: AsyncSession, quiz_in: QuizCreate, created_by: UUID) -> Quiz:
        db_quiz = Quiz(**quiz_in.model_dump(), created_by=created_by)
        db.add(db_quiz)
        await db.commit()
        
        # Trigger Notification
        await NotificationService.notify_students_for_new_quiz(db, db_quiz.course_id, db_quiz.id, db_quiz.title)
        
        # Re-fetch with relationships to avoid MissingGreenlet error in response serialization
        query = select(Quiz).options(selectinload(Quiz.questions).selectinload(Question.options)).where(Quiz.id == db_quiz.id)
        result = await db.execute(query)
        return result.scalars().first()

    @staticmethod
    async def add_questions(db: AsyncSession, quiz_id: UUID, questions_in: list[QuestionCreate]) -> list[Question]:
        created_questions = []
        for q_in in questions_in:
            db_question = Question(quiz_id=quiz_id, question_text=q_in.question_text, points=q_in.points)
            db.add(db_question)
            await db.flush() # Flush to get the question ID
            
            for opt_in in q_in.options:
                db_option = Option(
                    question_id=db_question.id,
                    option_text=opt_in.option_text,
                    is_correct=opt_in.is_correct
                )
                db.add(db_option)
            created_questions.append(db_question)
            
        await db.commit()
        
        # Re-fetch the created questions with options loaded
        question_ids = [q.id for q in created_questions]
        query = select(Question).options(selectinload(Question.options)).where(Question.id.in_(question_ids))
        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def get_quiz(db: AsyncSession, quiz_id: UUID) -> Quiz | None:
        query = select(Quiz).options(
            selectinload(Quiz.questions).selectinload(Question.options)
        ).where(Quiz.id == quiz_id)
        result = await db.execute(query)
        return result.scalars().first()

    @staticmethod
    async def get_attempt(db: AsyncSession, quiz_id: UUID, student_id: UUID) -> QuizAttempt | None:
        query = select(QuizAttempt).where(
            QuizAttempt.quiz_id == quiz_id,
            QuizAttempt.student_id == student_id
        )
        result = await db.execute(query)
        return result.scalars().first()

    @staticmethod
    async def submit_quiz(db: AsyncSession, quiz_id: UUID, student_id: UUID, submission: QuizSubmission):
        # Prevent multiple submissions
        existing_attempt = await QuizService.get_attempt(db, quiz_id, student_id)
        if existing_attempt:
            raise ValueError("You have already submitted this quiz.")
            
        # Get the quiz with questions and options to evaluate
        quiz = await QuizService.get_quiz(db, quiz_id)
        if not quiz:
            raise ValueError("Quiz not found.")

        # Map correct options
        correct_options_map = {}
        max_score = 0
        for q in quiz.questions:
            max_score += q.points
            # Allow multiple correct options, so we store a list of correct option IDs per question
            correct_options_map[q.id] = {str(opt.id): opt.is_correct for opt in q.options}

        total_score = 0
        answers_to_insert = []
        
        # Evaluate answers
        for answer in submission.answers:
            q_id = answer.question_id
            selected_opt_id = answer.selected_option_id
            
            # Find the question definition
            question_def = next((q for q in quiz.questions if q.id == q_id), None)
            if not question_def:
                continue

            # Check if selected option is correct
            if selected_opt_id:
                is_correct = correct_options_map.get(q_id, {}).get(str(selected_opt_id), False)
                if is_correct:
                    total_score += question_def.points

            # Prepare answer record
            answers_to_insert.append(
                QuizAttemptAnswer(
                    question_id=q_id,
                    selected_option_id=selected_opt_id
                )
            )

        # Create Attempt
        db_attempt = QuizAttempt(
            quiz_id=quiz_id,
            student_id=student_id,
            total_score=total_score,
            max_score=max_score,
            attempted_at=datetime.utcnow()
        )
        db.add(db_attempt)
        await db.flush()

        # Link answers to attempt and add them
        for ans in answers_to_insert:
            ans.attempt_id = db_attempt.id
            db.add(ans)

        await db.commit()
        await db.refresh(db_attempt)
        
        return {
            "attempt": db_attempt,
            "max_score": max_score
        }

    @staticmethod
    async def get_attempts(db: AsyncSession, user_id: UUID, role: str, quiz_id: UUID | None = None) -> list[QuizAttempt]:
        query = select(QuizAttempt).options(
            selectinload(QuizAttempt.quiz).selectinload(Quiz.questions), 
            selectinload(QuizAttempt.student)
        )
        
        if quiz_id:
            query = query.where(QuizAttempt.quiz_id == quiz_id)
            
        if role == UserRole.admin:
            pass # See all
        elif role == UserRole.teacher:
            # Attempts for quizzes they created or courses they teach
            query = query.join(Quiz).join(Course).join(Batch, isouter=True).where(
                or_(
                    Quiz.created_by == user_id,
                    Batch.teacher_id == user_id
                )
            )
        elif role == UserRole.student:
            query = query.join(Student).where(Student.user_id == user_id)
        elif role == UserRole.parent:
            query = query.join(Student).where(Student.parent_id == user_id)
        else:
            return []
            
        result = await db.execute(query)
        return result.scalars().all()
