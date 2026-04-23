from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional
from uuid import UUID
from app.db.models import Student
from app.schemas.student import StudentCreate, StudentUpdate

class StudentService:
    @staticmethod
    async def get_student(db: AsyncSession, student_id: UUID) -> Optional[Student]:
        result = await db.execute(select(Student).where(Student.id == student_id))
        return result.scalars().first()

    @staticmethod
    async def get_students(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[Student]:
        result = await db.execute(select(Student).offset(skip).limit(limit))
        return list(result.scalars().all())

    @staticmethod
    async def create_student(db: AsyncSession, student: StudentCreate) -> Student:
        db_student = Student(**student.model_dump())
        db.add(db_student)
        await db.commit()
        await db.refresh(db_student)
        return db_student
