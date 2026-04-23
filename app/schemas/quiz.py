from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from uuid import UUID
from datetime import datetime

# --- Options ---
class OptionBase(BaseModel):
    option_text: str
    model_config = ConfigDict(from_attributes=True)

class OptionCreate(OptionBase):
    is_correct: bool

class OptionResponse(OptionBase):
    id: UUID
    # We do not expose is_correct here to prevent cheating!
    
class OptionTeacherResponse(OptionBase):
    id: UUID
    is_correct: bool

# --- Questions ---
class QuestionBase(BaseModel):
    question_text: str
    points: int = 1
    model_config = ConfigDict(from_attributes=True)

class QuestionCreate(QuestionBase):
    options: List[OptionCreate]

class QuestionResponse(QuestionBase):
    id: UUID
    options: List[OptionResponse]

class QuestionTeacherResponse(QuestionBase):
    id: UUID
    options: List[OptionTeacherResponse]

# --- Quizzes ---
class QuizBase(BaseModel):
    title: str
    description: Optional[str] = None
    due_date: Optional[datetime] = None

class QuizCreate(QuizBase):
    course_id: UUID

class QuizResponse(QuizBase):
    id: UUID
    course_id: UUID
    created_at: datetime
    questions: Optional[List[QuestionResponse]] = None

    model_config = ConfigDict(from_attributes=True)

class QuizTeacherResponse(QuizBase):
    id: UUID
    course_id: UUID
    created_at: datetime
    questions: Optional[List[QuestionTeacherResponse]] = None

    model_config = ConfigDict(from_attributes=True)

# --- Submissions ---
class AnswerSubmission(BaseModel):
    question_id: UUID
    selected_option_id: Optional[UUID] = None

class QuizSubmission(BaseModel):
    answers: List[AnswerSubmission]

class QuizResultResponse(BaseModel):
    attempt_id: UUID
    quiz_id: UUID
    student_id: UUID
    total_score: int
    max_score: int
    attempted_at: datetime

    model_config = ConfigDict(from_attributes=True)

class QuizAttemptListResponse(BaseModel):
    id: UUID
    quiz_id: UUID
    quiz_title: str
    student_id: UUID
    student_name: str
    total_score: int
    max_score: int
    attempted_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class AnswerDetailResponse(BaseModel):
    question_text: str
    selected_option_text: Optional[str] = None
    correct_option_text: str
    is_correct: bool
    points_earned: int
    max_points: int

class QuizAttemptDetailResponse(BaseModel):
    id: UUID
    quiz_title: str
    student_name: str
    total_score: int
    max_score: int
    attempted_at: datetime
    answers: List[AnswerDetailResponse]

    model_config = ConfigDict(from_attributes=True)
