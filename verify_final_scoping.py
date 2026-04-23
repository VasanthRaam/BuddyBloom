import asyncio
import sys
from sqlalchemy.future import select
from app.db.database import AsyncSessionLocal
from app.db.models import User, Quiz
from app.services.quiz_service import QuizService

async def verify():
    if sys.stdout.encoding != 'utf-8':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        
    async with AsyncSessionLocal() as db:
        users = (await db.execute(select(User))).scalars().all()
        
        for u in users:
            print(f"\nUser: {u.email} (Role: {u.role})")
            quizzes = await QuizService.get_quizzes(db, u.id, u.role)
            print(f"Visible Quizzes: {len(quizzes)}")
            for q in quizzes:
                print(f" - {q.title}")

if __name__ == "__main__":
    asyncio.run(verify())
