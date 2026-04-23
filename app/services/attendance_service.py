from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update
from uuid import UUID
from datetime import date
from app.db.models import Attendance
from app.schemas.attendance import AttendanceBulkCreate

class AttendanceService:
    @staticmethod
    async def mark_bulk_attendance(db: AsyncSession, attendance_in: AttendanceBulkCreate) -> list[Attendance]:
        records = []
        for record_in in attendance_in.records:
            # Check if record already exists for this student on this date
            query = select(Attendance).where(
                Attendance.student_id == record_in.student_id,
                Attendance.date == attendance_in.date
            )
            result = await db.execute(query)
            existing_record = result.scalars().first()

            if existing_record:
                # Update existing record
                existing_record.status = record_in.status
                existing_record.remarks = record_in.remarks
                existing_record.batch_id = attendance_in.batch_id
                records.append(existing_record)
            else:
                # Create new record
                new_record = Attendance(
                    student_id=record_in.student_id,
                    batch_id=attendance_in.batch_id,
                    date=attendance_in.date,
                    status=record_in.status,
                    remarks=record_in.remarks
                )
                db.add(new_record)
                records.append(new_record)

        await db.commit()
        # Refresh all records to get IDs
        for record in records:
            await db.refresh(record)
        return records

    @staticmethod
    async def get_attendance(
        db: AsyncSession, 
        student_id: UUID | None = None, 
        batch_id: UUID | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        skip: int = 0, 
        limit: int = 100
    ):
        query = select(Attendance)
        
        if student_id:
            query = query.where(Attendance.student_id == student_id)
        if batch_id:
            query = query.where(Attendance.batch_id == batch_id)
        if start_date:
            query = query.where(Attendance.date >= start_date)
        if end_date:
            query = query.where(Attendance.date <= end_date)
            
        query = query.offset(skip).limit(limit)
        result = await db.execute(query)
        return result.scalars().all()
