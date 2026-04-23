import asyncio
from sqlalchemy import text
from app.db.database import engine

async def fix_schema():
    async with engine.begin() as conn:
        print("Adding teacher_id to batches...")
        await conn.execute(text('ALTER TABLE batches ADD COLUMN IF NOT EXISTS teacher_id UUID;'))
        
        print("Adding created_by to quizzes...")
        await conn.execute(text('ALTER TABLE quizzes ADD COLUMN IF NOT EXISTS created_by UUID;'))

        print("Adding max_score to quiz_attempts...")
        await conn.execute(text('ALTER TABLE quiz_attempts ADD COLUMN IF NOT EXISTS max_score INTEGER DEFAULT 0;'))
        
        print("Creating fee_payments table...")
        await conn.execute(text('''
            CREATE TABLE IF NOT EXISTS fee_payments (
                id UUID PRIMARY KEY,
                user_id UUID REFERENCES users(id) ON DELETE CASCADE,
                amount FLOAT NOT NULL,
                status VARCHAR DEFAULT 'pending',
                due_date TIMESTAMP WITH TIME ZONE,
                paid_at TIMESTAMP WITH TIME ZONE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
        '''))

        print("Creating homework table...")
        await conn.execute(text('''
            CREATE TABLE IF NOT EXISTS homework (
                id UUID PRIMARY KEY,
                teacher_id UUID REFERENCES users(id) ON DELETE CASCADE,
                batch_id UUID REFERENCES batches(id) ON DELETE CASCADE,
                student_id UUID REFERENCES users(id) ON DELETE SET NULL,
                title VARCHAR NOT NULL,
                description TEXT,
                due_date TIMESTAMP WITH TIME ZONE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
        '''))

        print("Adding student_id to homework table...")
        await conn.execute(text('ALTER TABLE homework ADD COLUMN IF NOT EXISTS student_id UUID REFERENCES users(id) ON DELETE SET NULL;'))
        
        print("Creating homework_submissions table...")
        await conn.execute(text('''
            CREATE TABLE IF NOT EXISTS homework_submissions (
                id UUID PRIMARY KEY,
                homework_id UUID REFERENCES homework(id) ON DELETE CASCADE,
                student_id UUID REFERENCES users(id) ON DELETE CASCADE,
                content TEXT,
                grade VARCHAR,
                submitted_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
        '''))
        
        print("Creating enrollments table...")
        await conn.execute(text('''
            CREATE TABLE IF NOT EXISTS enrollments (
                id UUID PRIMARY KEY,
                student_id UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
                batch_id UUID NOT NULL REFERENCES batches(id) ON DELETE CASCADE
            );
        '''))
        
        print("Adding enrolled_at to enrollments...")
        await conn.execute(text('ALTER TABLE enrollments ADD COLUMN IF NOT EXISTS enrolled_at TIMESTAMP WITH TIME ZONE DEFAULT now();'))
        
        print("Creating notifications table...")
        await conn.execute(text('''
            CREATE TABLE IF NOT EXISTS notifications (
                id UUID PRIMARY KEY,
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                link_to TEXT,
                is_read BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
            );
        '''))
        
    print("Schema updated successfully!")

if __name__ == "__main__":
    asyncio.run(fix_schema())
