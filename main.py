from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.api_v1.api import api_router

tags_metadata = [
    {
        "name": "users",
        "description": "Operations with users. The user ID matches the Supabase Auth UUID.",
    },
    {
        "name": "students",
        "description": "Manage student profiles and their relationships with parents.",
    },
]

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="BuddyBloom API - Academy Management Platform for Parents, Students, and Teachers.",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    openapi_tags=tags_metadata,
    docs_url="/docs",
    redoc_url="/redoc",
)

from app.core.middleware import SupabaseAuthMiddleware, NoCacheMiddleware, ResponseTimingMiddleware

# Add JWT Authentication and No-Cache Middleware
app.add_middleware(SupabaseAuthMiddleware)
app.add_middleware(NoCacheMiddleware)
app.add_middleware(ResponseTimingMiddleware)

# Set all CORS enabled origins
# Must be added LAST so it's the outermost middleware!
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://localhost:8081",
        "http://localhost:19006",
        "http://localhost:19000",
        "https://buddybloom.onrender.com",
        "https://buddybloom-dev.onrender.com",
        "https://vasanthacademy.com",
        "https://www.vasanthacademy.com",
        "https://buddybloom-prod-981707949514.asia-south1.run.app",
        "https://buddybloom-dev-981707949514.asia-south1.run.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)

@app.on_event("startup")
async def startup_event():
    try:
        from app.db.database import engine
        from sqlalchemy import text
        from app.db.models import Base
        async with engine.begin() as conn:
            # Create any missing tables (like user_push_tokens, expenses, etc.)
            await conn.run_sync(Base.metadata.create_all)
            # Ensure unique constraints on email are dropped to allow multiple users per email
            await conn.execute(text("ALTER TABLE users DROP CONSTRAINT IF EXISTS users_email_key;"))
            await conn.execute(text("ALTER TABLE pending_registrations DROP CONSTRAINT IF EXISTS pending_registrations_email_key;"))
            # Ensure new columns exist on pending_registrations table
            await conn.execute(text("ALTER TABLE pending_registrations ADD COLUMN IF NOT EXISTS push_token VARCHAR;"))
            await conn.execute(text("ALTER TABLE pending_registrations ADD COLUMN IF NOT EXISTS selected_course_ids UUID[];"))
            await conn.execute(text("ALTER TABLE pending_registrations ADD COLUMN IF NOT EXISTS selected_batch_ids UUID[];"))
            await conn.execute(text("ALTER TABLE pending_registrations ADD COLUMN IF NOT EXISTS mother_name VARCHAR;"))
            await conn.execute(text("ALTER TABLE pending_registrations ADD COLUMN IF NOT EXISTS father_name VARCHAR;"))
            await conn.execute(text("ALTER TABLE pending_registrations ADD COLUMN IF NOT EXISTS parent_phone_number VARCHAR;"))
            await conn.execute(text("ALTER TABLE pending_registrations ADD COLUMN IF NOT EXISTS dob DATE;"))
            await conn.execute(text("ALTER TABLE pending_registrations ADD COLUMN IF NOT EXISTS education_qualification VARCHAR;"))
            await conn.execute(text("ALTER TABLE pending_registrations ADD COLUMN IF NOT EXISTS profile_picture TEXT;"))
            # Ensure upi_id and new fields on users table
            await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS upi_id VARCHAR;"))
            await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS dob DATE;"))
            await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS education_qualification VARCHAR;"))
            await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS profile_picture TEXT;"))
            # Ensure new fields on students table
            await conn.execute(text("ALTER TABLE students ADD COLUMN IF NOT EXISTS mother_name VARCHAR;"))
            await conn.execute(text("ALTER TABLE students ADD COLUMN IF NOT EXISTS father_name VARCHAR;"))
            await conn.execute(text("ALTER TABLE students ADD COLUMN IF NOT EXISTS parent_phone_number VARCHAR;"))
            # Ensure course_id and batch_id columns exist on fee_payments table
            await conn.execute(text("ALTER TABLE fee_payments ADD COLUMN IF NOT EXISTS course_id UUID;"))
            await conn.execute(text("ALTER TABLE fee_payments ADD COLUMN IF NOT EXISTS batch_id UUID;"))
            # Ensure is_manual column exists on fee_payments table
            await conn.execute(text("ALTER TABLE fee_payments ADD COLUMN IF NOT EXISTS is_manual BOOLEAN NOT NULL DEFAULT FALSE;"))
            # Ensure student_id column exists on incomes table
            await conn.execute(text("ALTER TABLE incomes ADD COLUMN IF NOT EXISTS student_id UUID;"))

            # ── XP System Rewards Tables ──────────────────────────────────────
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS point_transactions (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    student_id UUID REFERENCES students(id) ON DELETE CASCADE,
                    points INTEGER NOT NULL,
                    source VARCHAR(50) NOT NULL,
                    reason TEXT,
                    quiz_attempt_id UUID REFERENCES quiz_attempts(id) ON DELETE SET NULL,
                    given_by UUID REFERENCES users(id) ON DELETE SET NULL,
                    created_at TIMESTAMPTZ DEFAULT now()
                );
            """))
            await conn.execute(text("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_point_txn_quiz_attempt
                ON point_transactions(student_id, quiz_attempt_id)
                WHERE quiz_attempt_id IS NOT NULL AND source = 'quiz';
            """))
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS teacher_wallets (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    teacher_id UUID UNIQUE REFERENCES users(id) ON DELETE CASCADE,
                    total_points INTEGER NOT NULL DEFAULT 1000,
                    remaining_points INTEGER NOT NULL DEFAULT 1000,
                    distributed_points INTEGER NOT NULL DEFAULT 0,
                    month_year VARCHAR(7) NOT NULL,
                    expires_at TIMESTAMPTZ,
                    last_reset_at TIMESTAMPTZ DEFAULT now()
                );
            """))
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS reward_catalog (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    title VARCHAR NOT NULL,
                    description TEXT,
                    points_required INTEGER NOT NULL,
                    image_url TEXT,
                    is_active BOOLEAN NOT NULL DEFAULT true,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMPTZ DEFAULT now()
                );
            """))
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS reward_redemptions (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    student_id UUID REFERENCES students(id) ON DELETE CASCADE,
                    reward_id UUID REFERENCES reward_catalog(id) ON DELETE CASCADE,
                    points_spent INTEGER NOT NULL,
                    status VARCHAR NOT NULL DEFAULT 'pending',
                    admin_note TEXT,
                    redeemed_at TIMESTAMPTZ DEFAULT now(),
                    updated_at TIMESTAMPTZ DEFAULT now()
                );
            """))
            # Seed default reward catalog items if empty
            count_res = await conn.execute(text("SELECT COUNT(*) FROM reward_catalog;"))
            if count_res.scalar() == 0:
                await conn.execute(text("""
                    INSERT INTO reward_catalog (id, title, description, points_required, image_url, sort_order) VALUES
                    (gen_random_uuid(), '3 Months Tuition Fee Waiver', 'Get 3 months of tuition fees waived as a top performer!', 50000, NULL, 1),
                    (gen_random_uuid(), 'Premium Smart Watch', 'A premium smartwatch to reward your dedication.', 30000, NULL, 2),
                    (gen_random_uuid(), 'Premium Stationery Kit', 'High-quality stationery set for serious students.', 20000, NULL, 3),
                    (gen_random_uuid(), 'Bluetooth Headphones', 'Wireless headphones to make studying more enjoyable.', 10000, NULL, 4),
                    (gen_random_uuid(), 'Study Essentials Pack', 'Notebooks, pens, and organizers to kickstart success.', 5000, NULL, 5);
                """))
                print("[XP System] Seeded default reward catalog items.")

            # ── Performance Indexes ──────────────────────────────────────────
            print("[DB Migration] Checking/applying performance B-Tree indexes...")
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_students_parent_id ON students(parent_id);"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_students_user_id ON students(user_id);"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_batches_course_id ON batches(course_id);"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_batches_teacher_id ON batches(teacher_id);"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_attendance_student_date ON attendance(student_id, date);"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_attendance_batch_date ON attendance(batch_id, date);"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_quizzes_course_id ON quizzes(course_id);"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_quizzes_created_by ON quizzes(created_by);"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_questions_quiz_id ON questions(quiz_id);"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_options_question_id ON options(question_id);"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_quiz_attempts_quiz_student ON quiz_attempts(quiz_id, student_id);"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_quiz_attempt_answers_attempt_question ON quiz_attempt_answers(attempt_id, question_id);"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_fee_payments_user_status ON fee_payments(user_id, status);"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_homework_batch_id ON homework(batch_id);"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_homework_teacher_id ON homework(teacher_id);"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_homework_submissions_homework_student ON homework_submissions(homework_id, student_id);"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_notifications_user_created ON notifications(user_id, created_at DESC);"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_notifications_user_unread ON notifications(user_id) WHERE is_read = false;"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_enrollments_student_batch ON enrollments(student_id, batch_id);"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_point_transactions_student ON point_transactions(student_id);"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_chat_messages_user_created ON chat_messages(user_id, created_at);"))
            print("[DB Migration] Performance indexes check completed.")

            print("Successfully ran startup database migrations!")

    except Exception as e:
        print(f"Error during startup database migrations: {e}")

@app.get("/")
def root():
    return {"message": "Welcome to the BuddyBloom API"}
