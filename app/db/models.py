import enum
import uuid
from sqlalchemy import Column, String, Date, DateTime, ForeignKey, Enum, Text, Integer, Boolean, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.database import Base

class UserRole(str, enum.Enum):
    admin = "admin"
    teacher = "teacher"
    parent = "parent"
    student = "student"

class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    role = Column(Enum(UserRole, name="user_role"), nullable=False, index=True)
    full_name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    phone = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    is_approved = Column(Boolean, default=False, server_default="false", nullable=False)
    upi_id = Column(String, nullable=True)
    dob = Column(Date, nullable=True)
    education_qualification = Column(String, nullable=True)
    profile_picture = Column(Text, nullable=True)

    # Relationships
    students_as_parent = relationship("Student", back_populates="parent", foreign_keys="[Student.parent_id]")
    student_profile = relationship("Student", back_populates="user", uselist=False, foreign_keys="[Student.user_id]")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    fee_payments = relationship("FeePayment", back_populates="user", cascade="all, delete-orphan")
    homework_submissions = relationship("HomeworkSubmission", back_populates="student", cascade="all, delete-orphan")


from sqlalchemy.dialects.postgresql import UUID, ARRAY

class PendingRegistration(Base):
    """Holds registrations waiting for Admin approval.
    Password is stored temporarily in plain-text only until approval.
    Once approved, Supabase Auth is used and this record is deleted.
    """
    __tablename__ = "pending_registrations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    full_name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    # We store the raw password temporarily so the admin can create the Supabase
    # Auth account on approval. This record is deleted immediately after approval.
    hashed_temp_password = Column(String, nullable=False)
    role = Column(Enum(UserRole, name="user_role"), nullable=False)
    status = Column(String, default="pending")  # pending | approved | rejected
    rejection_reason = Column(String, nullable=True)
    
    # New fields for course/batch selection
    selected_course_ids = Column(ARRAY(UUID(as_uuid=True)), nullable=True)
    selected_batch_ids = Column(ARRAY(UUID(as_uuid=True)), nullable=True)
    push_token = Column(String, nullable=True)
    
    # Extra fields for detailed registration
    mother_name = Column(String, nullable=True)
    father_name = Column(String, nullable=True)
    parent_phone_number = Column(String, nullable=True)
    dob = Column(Date, nullable=True)
    education_qualification = Column(String, nullable=True)
    profile_picture = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Student(Base):
    __tablename__ = "students"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    parent_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), unique=True, nullable=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    date_of_birth = Column(Date)
    mother_name = Column(String, nullable=True)
    father_name = Column(String, nullable=True)
    parent_phone_number = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    parent = relationship("User", back_populates="students_as_parent", foreign_keys=[parent_id])
    user = relationship("User", back_populates="student_profile", foreign_keys=[user_id])
    attendance_records = relationship("Attendance", back_populates="student", cascade="all, delete-orphan")
    enrollments = relationship("Enrollment", back_populates="student", cascade="all, delete-orphan")

class AttendanceStatus(str, enum.Enum):
    present = "present"
    absent = "absent"
    late = "late"
    excused = "excused"

class Course(Base):
    __tablename__ = "courses"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    description = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    batches = relationship("Batch", back_populates="course", cascade="all, delete-orphan")

class Batch(Base):
    __tablename__ = "batches"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    course_id = Column(UUID(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    teacher_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    name = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    course = relationship("Course", back_populates="batches")
    teacher = relationship("User", backref="assigned_batches")
    attendance_records = relationship("Attendance", back_populates="batch", cascade="all, delete-orphan")
    enrollments = relationship("Enrollment", back_populates="batch", cascade="all, delete-orphan")

class Attendance(Base):
    __tablename__ = "attendance"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    batch_id = Column(UUID(as_uuid=True), ForeignKey("batches.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(Date, nullable=False)
    status = Column(Enum(AttendanceStatus, name="attendance_status"), nullable=False)
    remarks = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    student = relationship("Student", back_populates="attendance_records")
    batch = relationship("Batch", back_populates="attendance_records")

class Quiz(Base):
    __tablename__ = "quizzes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    course_id = Column(UUID(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text)
    due_date = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
 
    # Relationships
    course = relationship("Course", backref="quizzes")
    creator = relationship("User", backref="created_quizzes")
    questions = relationship("Question", back_populates="quiz", cascade="all, delete-orphan")
    attempts = relationship("QuizAttempt", back_populates="quiz", cascade="all, delete-orphan")

class Question(Base):
    __tablename__ = "questions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    quiz_id = Column(UUID(as_uuid=True), ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False, index=True)
    question_text = Column(Text, nullable=False)
    points = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    quiz = relationship("Quiz", back_populates="questions")
    options = relationship("Option", back_populates="question", cascade="all, delete-orphan")
    answers = relationship("QuizAttemptAnswer", back_populates="question")

class Option(Base):
    __tablename__ = "options"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question_id = Column(UUID(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True)
    option_text = Column(Text, nullable=False)
    is_correct = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    question = relationship("Question", back_populates="options")

class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    quiz_id = Column(UUID(as_uuid=True), ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    total_score = Column(Integer, nullable=False, default=0)
    max_score = Column(Integer, nullable=False, default=0)
    attempted_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    quiz = relationship("Quiz", back_populates="attempts")
    student = relationship("Student", backref="quiz_attempts")
    answers = relationship("QuizAttemptAnswer", back_populates="attempt", cascade="all, delete-orphan")

class QuizAttemptAnswer(Base):
    __tablename__ = "quiz_attempt_answers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attempt_id = Column(UUID(as_uuid=True), ForeignKey("quiz_attempts.id", ondelete="CASCADE"), nullable=False, index=True)
    question_id = Column(UUID(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True)
    selected_option_id = Column(UUID(as_uuid=True), ForeignKey("options.id", ondelete="SET NULL"), nullable=True)
    
    # Relationships
    attempt = relationship("QuizAttempt", back_populates="answers")
    question = relationship("Question", back_populates="answers")
    selected_option = relationship("Option")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class FeePayment(Base):
    __tablename__ = "fee_payments"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    status = Column(String, default="pending") # pending, paid
    due_date = Column(DateTime(timezone=True))
    paid_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    course_id = Column(UUID(as_uuid=True), ForeignKey("courses.id", ondelete="SET NULL"), nullable=True)
    batch_id = Column(UUID(as_uuid=True), ForeignKey("batches.id", ondelete="SET NULL"), nullable=True)
    is_manual = Column(Boolean, default=False, server_default="false", nullable=False)

    user = relationship("User", back_populates="fee_payments")
    course = relationship("Course")
    batch = relationship("Batch")

class Homework(Base):
    __tablename__ = "homework"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    teacher_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    batch_id = Column(UUID(as_uuid=True), ForeignKey("batches.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    title = Column(String, nullable=False)
    description = Column(Text)
    due_date = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    teacher = relationship("User", foreign_keys=[teacher_id])
    student = relationship("User", foreign_keys=[student_id])
    batch = relationship("Batch")
    submissions = relationship("HomeworkSubmission", back_populates="homework")

class HomeworkSubmission(Base):
    __tablename__ = "homework_submissions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    homework_id = Column(UUID(as_uuid=True), ForeignKey("homework.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    content = Column(Text)
    grade = Column(String, nullable=True)
    is_completed = Column(Boolean, default=False, server_default="false")
    submitted_at = Column(DateTime(timezone=True), server_default=func.now())

    homework = relationship("Homework", back_populates="submissions")
    student = relationship("User", back_populates="homework_submissions")

class ProgressTracking(Base):
    __tablename__ = "progress_tracking"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    course_id = Column(UUID(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    milestone_name = Column(String, nullable=False)
    evaluation_score = Column(Integer, nullable=True)
    remarks = Column(Text, nullable=True)
    recorded_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    recorded_date = Column(Date, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    student = relationship("Student", backref="progress_records")
    course = relationship("Course")
    recorder = relationship("User")
class Notification(Base):
    __tablename__ = "notifications"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    link_to = Column(String, nullable=True) # e.g. "Quiz:uuid"
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="notifications")

class Enrollment(Base):
    __tablename__ = "enrollments"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    batch_id = Column(UUID(as_uuid=True), ForeignKey("batches.id", ondelete="CASCADE"), nullable=False, index=True)
    enrolled_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    student = relationship("Student", back_populates="enrollments")
    batch = relationship("Batch", back_populates="enrollments")

class Expense(Base):
    __tablename__ = "expenses"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    amount = Column(Float, nullable=False)
    category = Column(String, nullable=False) # e.g. Salary, Maintenance, Other
    description = Column(String)
    expense_date = Column(Date, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

class Income(Base):
    __tablename__ = "incomes"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    amount = Column(Float, nullable=False)
    category = Column(String, nullable=False) # e.g. Event, Course Fee, Donation, Other
    description = Column(String)
    income_date = Column(Date, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    student_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

class AcademyHoliday(Base):
    __tablename__ = "academy_holidays"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    date = Column(Date, unique=True, nullable=False)
    description = Column(String, nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class UserPushToken(Base):
    __tablename__ = "user_push_tokens"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    push_token = Column(String, unique=True, nullable=False)
    device_type = Column(String, nullable=True) # e.g. "android", "ios"
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    user = relationship("User", backref="push_tokens")


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String, nullable=False)  # "user" or "model"
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    user = relationship("User", backref="chat_messages")


class PendingEnrollment(Base):
    __tablename__ = "pending_enrollments"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    batch_id = Column(UUID(as_uuid=True), ForeignKey("batches.id", ondelete="CASCADE"), nullable=False)
    status = Column(String, default="pending")  # pending, approved, rejected
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    student = relationship("Student")
    batch = relationship("Batch")


class LeaveRequest(Base):
    __tablename__ = "leave_requests"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    reason = Column(Text, nullable=False)
    status = Column(String, default="pending")  # pending, approved, rejected
    handled_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    student = relationship("Student")
    handler = relationship("User")

class PasswordResetOTP(Base):
    __tablename__ = "password_reset_otps"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, nullable=False)
    otp = Column(String(6), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_used = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class MobileLoginOTP(Base):
    __tablename__ = "mobile_login_otps"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    phone = Column(String, nullable=False)
    otp = Column(String(6), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_used = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Lead(Base):
    __tablename__ = "leads"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    phone = Column(String(50), nullable=False)
    course = Column(String(100), nullable=False)
    batch = Column(String(50), nullable=False)  # "trichy" or "vaiyampatti"
    message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ──────────────────────────────────────────────────────────────────────────────
# XP Rewards System
# ──────────────────────────────────────────────────────────────────────────────

class PointTransaction(Base):
    """
    Records every XP credit or debit for a student.
    Sources: 'quiz' (auto-awarded after quiz), 'teacher' (manual award), 'admin', 'redemption' (debit).
    The quiz_attempt_id carries a UNIQUE constraint to prevent double-awarding the same quiz attempt.
    """
    __tablename__ = "point_transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    points = Column(Integer, nullable=False)  # positive = credit, negative = debit
    source = Column(String(50), nullable=False)  # 'quiz', 'teacher', 'admin', 'redemption'
    reason = Column(Text, nullable=True)
    quiz_attempt_id = Column(UUID(as_uuid=True), ForeignKey("quiz_attempts.id", ondelete="SET NULL"), nullable=True)
    given_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    student = relationship("Student", backref="point_transactions")
    giver = relationship("User", foreign_keys=[given_by])


class TeacherWallet(Base):
    """
    Monthly XP point wallet for teachers.
    Resets to 1000 on the 1st of every month. Unused points expire.
    """
    __tablename__ = "teacher_wallets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    teacher_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    total_points = Column(Integer, nullable=False, default=1000)
    remaining_points = Column(Integer, nullable=False, default=1000)
    distributed_points = Column(Integer, nullable=False, default=0)
    month_year = Column(String(7), nullable=False)  # e.g. '2026-07'
    expires_at = Column(DateTime(timezone=True), nullable=True)
    last_reset_at = Column(DateTime(timezone=True), server_default=func.now())

    teacher = relationship("User", backref="xp_wallet")


class RewardCatalog(Base):
    """
    Admin-configurable list of rewards that students can redeem with their XP points.
    """
    __tablename__ = "reward_catalog"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    points_required = Column(Integer, nullable=False)
    image_url = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, server_default="true", nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    redemptions = relationship("RewardRedemption", back_populates="reward", cascade="all, delete-orphan")


class RewardRedemption(Base):
    """
    Tracks student reward redemption requests.
    When a student redeems a reward, points are debited via PointTransaction and this record is created.
    """
    __tablename__ = "reward_redemptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    reward_id = Column(UUID(as_uuid=True), ForeignKey("reward_catalog.id", ondelete="CASCADE"), nullable=False)
    points_spent = Column(Integer, nullable=False)
    status = Column(String, default="pending", nullable=False)  # pending, approved, rejected
    admin_note = Column(Text, nullable=True)
    redeemed_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    student = relationship("Student", backref="reward_redemptions")
    reward = relationship("RewardCatalog", back_populates="redemptions")

