import asyncio
import sys
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from app.db.database import AsyncSessionLocal
from app.db.models import Quiz, Question, Option

async def check_details():
    if sys.stdout.encoding != 'utf-8':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(Quiz).options(selectinload(Quiz.questions).selectinload(Question.options)))
        quizzes = res.scalars().all()
        
        print(f"Total Quizzes: {len(quizzes)}")
        for q in quizzes:
            print(f"\nQuiz: {q.title} (ID: {q.id})")
            print(f"Questions: {len(q.questions)}")
            for ques in q.questions:
                print(f" - Q: {ques.question_text}")
                print(f"   Options: {len(ques.options)}")
                for opt in ques.options:
                    print(f"     * {opt.option_text} (Correct: {opt.is_correct})")

if __name__ == "__main__":
    asyncio.run(check_details())
