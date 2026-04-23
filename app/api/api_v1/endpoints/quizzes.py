from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from uuid import UUID

from app.db.database import get_db
from app.db.models import Quiz, Question
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from app.schemas.quiz import (
    QuizCreate, QuizResponse, QuizTeacherResponse, 
    QuestionCreate, QuestionTeacherResponse,
    QuizSubmission, QuizResultResponse, QuizAttemptListResponse,
    QuizAttemptDetailResponse
)
from app.services.quiz_service import QuizService
from app.api.deps import get_current_user, RequireRole

router = APIRouter()

@router.get("/", response_model=List[QuizResponse])
async def list_quizzes(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    List all available quizzes.
    """
    print(f"🔍 [DEBUG] Fetching quizzes for User: {current_user['id']} (Role: {current_user['role']})")
    quizzes = await QuizService.get_quizzes(db, current_user["id"], current_user["role"])
    print(f"🔍 [DEBUG] Found {len(quizzes)} quizzes")
    return quizzes

@router.post("/", response_model=QuizResponse, status_code=status.HTTP_201_CREATED)
async def create_quiz(
    quiz_in: QuizCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(RequireRole(["teacher", "admin"]))
):
    """
    Create a new quiz. Only accessible by teachers and admins.
    """
    # Teacher scope check (simplified: check if they teach any batch of this course)
    if current_user["role"] == "teacher":
        from app.db.models import Batch
        from sqlalchemy.future import select
        res = await db.execute(select(Batch).where(Batch.course_id == quiz_in.course_id, Batch.teacher_id == current_user["id"]))
        if not res.scalars().first():
             raise HTTPException(status_code=403, detail="You can only create quizzes for courses you teach.")

    try:
        return await QuizService.create_quiz(db, quiz_in, current_user["id"])
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{quiz_id}/questions", response_model=List[QuestionTeacherResponse])
async def add_questions(
    quiz_id: UUID,
    questions_in: List[QuestionCreate],
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(RequireRole(["teacher", "admin"]))
):
    """
    Add multiple questions with options to a quiz. Only accessible by teachers and admins.
    """
    quiz = await QuizService.get_quiz(db, quiz_id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
        
    try:
        return await QuizService.add_questions(db, quiz_id, questions_in)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{quiz_id}")
async def get_quiz(
    quiz_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Get quiz details. 
    Teachers see the correct answers (is_correct flag).
    Students only see the options without the correct answers.
    """
    quiz = await QuizService.get_quiz(db, quiz_id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
        
    if current_user.get("role") in ["teacher", "admin"]:
        return QuizTeacherResponse.model_validate(quiz)
    else:
        return QuizResponse.model_validate(quiz)

@router.post("/{quiz_id}/submit", response_model=QuizResultResponse)
async def submit_quiz(
    quiz_id: UUID,
    submission: QuizSubmission,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(RequireRole(["student"]))
):
    """
    Submit a quiz attempt. Only accessible by students.
    Automatically evaluates the score.
    """
    # Find the student profile ID using the current_user's UUID
    # Since we need the student_id from the students table, we fetch it here.
    from app.db.models import Student
    from sqlalchemy.future import select
    
    result = await db.execute(select(Student).where(Student.user_id == current_user["id"]))
    student = result.scalars().first()
    
    if not student:
        # Fallback to check if their ID matches student ID directly (for our test setup)
        result = await db.execute(select(Student).where(Student.id == current_user["id"]))
        student = result.scalars().first()
        if not student:
            raise HTTPException(status_code=404, detail="Student profile not found")

    try:
        eval_result = await QuizService.submit_quiz(db, quiz_id, student.id, submission)
        attempt = eval_result["attempt"]
        
        return QuizResultResponse(
            attempt_id=attempt.id,
            quiz_id=attempt.quiz_id,
            student_id=attempt.student_id,
            total_score=attempt.total_score,
            max_score=eval_result["max_score"],
            attempted_at=attempt.attempted_at
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/results/all", response_model=List[QuizAttemptListResponse])
async def get_all_results(
    quiz_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Get quiz results (attempts). 
    Everyone can view, but parents are restricted to their kids.
    """
    attempts = await QuizService.get_attempts(db, current_user["id"], current_user["role"], quiz_id)
    
    results_formatted = []
    for a in attempts:
        m_score = a.max_score
        if not m_score or m_score == 0:
            m_score = sum(q.points for q in a.quiz.questions)
            
        results_formatted.append(
            QuizAttemptListResponse(
                id=a.id,
                quiz_id=a.quiz_id,
                quiz_title=a.quiz.title,
                student_id=a.student_id,
                student_name=f"{a.student.first_name} {a.student.last_name}",
                total_score=a.total_score,
                max_score=m_score,
                attempted_at=a.attempted_at
            )
        )
    return results_formatted
@router.get("/attempts/{attempt_id}/details", response_model=QuizAttemptDetailResponse)
async def get_attempt_details(
    attempt_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Get detailed breakdown of a quiz attempt (questions, student's answers, and correctness).
    """
    from app.db.models import QuizAttempt, QuizAttemptAnswer, Question, Option, Student, Quiz
    from sqlalchemy.orm import selectinload
    
    query = (
        select(QuizAttempt)
        .options(
            selectinload(QuizAttempt.quiz),
            selectinload(QuizAttempt.student),
            selectinload(QuizAttempt.answers).selectinload(QuizAttemptAnswer.question),
            selectinload(QuizAttempt.answers).selectinload(QuizAttemptAnswer.selected_option)
        )
        .where(QuizAttempt.id == attempt_id)
    )
    
    result = await db.execute(query)
    attempt = result.scalars().first()
    
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")
        
    # Role check: Student can only see their own, Parent can only see their child's, Staff see all
    if current_user["role"] == "student":
        if str(attempt.student.user_id) != current_user["id"]:
            raise HTTPException(status_code=403, detail="Not authorized to view this result")
    elif current_user["role"] == "parent":
        if str(attempt.student.parent_id) != current_user["id"]:
            raise HTTPException(status_code=403, detail="Not authorized to view this result")
    elif current_user["role"] not in ["admin", "teacher"]:
        raise HTTPException(status_code=403, detail="Not authorized to view this result")

    # Fetch correct options for all questions in this quiz
    quiz_query = select(Quiz).options(selectinload(Quiz.questions).selectinload(Question.options)).where(Quiz.id == attempt.quiz_id)
    quiz_res = await db.execute(quiz_query)
    quiz = quiz_res.scalars().first()
    
    correct_map = {}
    for q in quiz.questions:
        correct_opt = next((o for o in q.options if o.is_correct), None)
        correct_map[q.id] = {
            "text": correct_opt.option_text if correct_opt else "N/A",
            "max_points": q.points
        }

    answer_details = []
    for ans in attempt.answers:
        info = correct_map.get(ans.question_id, {"text": "N/A", "max_points": 0})
        is_correct = ans.selected_option.is_correct if ans.selected_option else False
        
        answer_details.append({
            "question_text": ans.question.question_text,
            "selected_option_text": ans.selected_option.option_text if ans.selected_option else "Not Answered",
            "correct_option_text": info["text"],
            "is_correct": is_correct,
            "points_earned": ans.question.points if is_correct else 0,
            "max_points": ans.question.points
        })

    m_score = attempt.max_score
    if not m_score or m_score == 0:
        m_score = sum(q.points for q in attempt.quiz.questions)

    return {
        "id": attempt.id,
        "quiz_title": attempt.quiz.title,
        "student_name": f"{attempt.student.first_name} {attempt.student.last_name}",
        "total_score": attempt.total_score,
        "max_score": m_score,
        "attempted_at": attempt.attempted_at,
        "answers": answer_details
    }
