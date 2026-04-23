import asyncio
from uuid import uuid4
from sqlalchemy.future import select
from app.db.database import AsyncSessionLocal
from app.db.models import Quiz, Question, Option, Course

async def setup_quiz():
    async with AsyncSessionLocal() as db:
        # 1. Get or Create a Course
        result = await db.execute(select(Course).limit(1))
        course = result.scalars().first()
        if not course:
            course = Course(id=uuid4(), name="General Science", description="Basic science for kids")
            db.add(course)
            await db.flush()
        
        # 2. Create a Quiz
        quiz = Quiz(
            id=uuid4(),
            course_id=course.id,
            title="Animal Kingdom Adventure! 🦁",
            description="How much do you know about your favorite animals?"
        )
        db.add(quiz)
        await db.flush()

        # 3. Add Questions
        q1 = Question(quiz_id=quiz.id, question_text="Which animal is known as the King of the Jungle?", points=10)
        db.add(q1)
        await db.flush()
        db.add_all([
            Option(question_id=q1.id, option_text="Lion 🦁", is_correct=True),
            Option(question_id=q1.id, option_text="Elephant 🐘", is_correct=False),
            Option(question_id=q1.id, option_text="Giraffe 🦒", is_correct=False),
            Option(question_id=q1.id, option_text="Monkey 🐒", is_correct=False),
        ])

        q2 = Question(quiz_id=quiz.id, question_text="What do pandas love to eat?", points=10)
        db.add(q2)
        await db.flush()
        db.add_all([
            Option(question_id=q2.id, option_text="Pizza 🍕", is_correct=False),
            Option(question_id=q2.id, option_text="Bamboo 🎋", is_correct=True),
            Option(question_id=q2.id, option_text="Fish 🐟", is_correct=False),
            Option(question_id=q2.id, option_text="Carrots 🥕", is_correct=False),
        ])

        q3 = Question(quiz_id=quiz.id, question_text="Which of these animals can fly?", points=10)
        db.add(q3)
        await db.flush()
        db.add_all([
            Option(question_id=q3.id, option_text="Penguin 🐧", is_correct=False),
            Option(question_id=q3.id, option_text="Owl 🦉", is_correct=True),
            Option(question_id=q3.id, option_text="Kangaroo 🦘", is_correct=False),
            Option(question_id=q3.id, option_text="Crocodile 🐊", is_correct=False),
        ])

        await db.commit()
        print(f"Sample quiz created: {quiz.title}")

if __name__ == "__main__":
    asyncio.run(setup_quiz())
