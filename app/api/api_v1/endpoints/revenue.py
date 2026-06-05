from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Any
from uuid import UUID
from collections import defaultdict
import datetime

from app.db.database import get_db
from app.db.models import User, FeePayment, UserRole, Expense, Student, Enrollment, Batch, Course
from app.api.deps import get_current_user
from app.schemas.revenue import ExpenseCreate, ExpenseResponse, RevenueDashboardData

router = APIRouter()

@router.post("/expenses", response_model=ExpenseResponse)
async def create_expense(
    *,
    db: AsyncSession = Depends(get_db),
    expense_in: ExpenseCreate,
    current_user: dict = Depends(get_current_user)
) -> Any:
    """
    Create a new expense. Admin only.
    """
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Not enough permissions")

    expense = Expense(
        amount=expense_in.amount,
        category=expense_in.category,
        description=expense_in.description,
        expense_date=expense_in.expense_date,
        created_by=UUID(current_user["id"])
    )
    db.add(expense)
    await db.commit()
    await db.refresh(expense)
    return expense

@router.get("/expenses", response_model=List[ExpenseResponse])
async def get_expenses(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
) -> Any:
    """
    Get all expenses. Admin only.
    """
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Not enough permissions")

    result = await db.execute(select(Expense).order_by(Expense.expense_date.desc()))
    return result.scalars().all()

@router.get("/dashboard", response_model=RevenueDashboardData)
async def get_revenue_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
) -> Any:
    """
    Get revenue dashboard data including income, expenses, and breakdowns. Admin only.
    """
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Not enough permissions")

    # Fetch Income
    paid_fees_res = await db.execute(select(FeePayment).where(FeePayment.status == 'paid'))
    paid_fees = paid_fees_res.scalars().all()
    total_income = sum(fee.amount for fee in paid_fees)

    # Fetch Expenses
    expenses_res = await db.execute(select(Expense))
    expenses = expenses_res.scalars().all()
    total_expenses = sum(exp.amount for exp in expenses)

    net_profit = total_income - total_expenses

    # Monthly Aggregation
    monthly_dict = defaultdict(lambda: {"income": 0.0, "expense": 0.0})
    
    for fee in paid_fees:
        if fee.paid_at:
            month_key = fee.paid_at.strftime("%Y-%m")
            monthly_dict[month_key]["income"] += fee.amount

    for exp in expenses:
        if exp.expense_date:
            month_key = exp.expense_date.strftime("%Y-%m")
            monthly_dict[month_key]["expense"] += exp.amount

    # Convert to list and sort
    monthly_data = []
    for month in sorted(monthly_dict.keys()):
        monthly_data.append({
            "month": month,
            "income": monthly_dict[month]["income"],
            "expense": monthly_dict[month]["expense"]
        })

    # Course/Batch Breakdown
    # A fee payment is linked to a user_id (student). We need to find their enrollments.
    course_dict = defaultdict(float)
    batch_dict = defaultdict(float)

    for fee in paid_fees:
        # If the fee is explicitly linked to a course and/or batch, attribute the entire amount directly
        if fee.course_id or fee.batch_id:
            batch = None
            if fee.batch_id:
                batch_res = await db.execute(select(Batch).where(Batch.id == fee.batch_id))
                batch = batch_res.scalars().first()
                if batch:
                    batch_dict[batch.name] += fee.amount
            if fee.course_id:
                course_res = await db.execute(select(Course).where(Course.id == fee.course_id))
                course = course_res.scalars().first()
                if course:
                    course_dict[course.name] += fee.amount
            elif batch: # fallback if course_id is null but batch_id is set
                course_res = await db.execute(select(Course).where(Course.id == batch.course_id))
                course = course_res.scalars().first()
                if course:
                    course_dict[course.name] += fee.amount
            continue

        # Fallback for historical fee payments (split evenly across student's enrollments)
        student_res = await db.execute(select(Student).where(Student.user_id == fee.user_id))
        student = student_res.scalars().first()
        if not student:
            continue
            
        # Find enrollments
        enrollments_res = await db.execute(select(Enrollment).where(Enrollment.student_id == student.id))
        enrollments = enrollments_res.scalars().all()
        if not enrollments:
            continue
            
        # Split fee amount evenly across enrolled batches for revenue attribution
        split_amount = fee.amount / len(enrollments)
        
        for enr in enrollments:
            batch_res = await db.execute(select(Batch).where(Batch.id == enr.batch_id))
            batch = batch_res.scalars().first()
            if batch:
                batch_dict[batch.name] += split_amount
                course_res = await db.execute(select(Course).where(Course.id == batch.course_id))
                course = course_res.scalars().first()
                if course:
                    course_dict[course.name] += split_amount

    # Convert to BreakdownItem format
    course_breakdown = []
    for name, amt in course_dict.items():
        percentage = (amt / total_income * 100) if total_income > 0 else 0
        course_breakdown.append({"name": name, "amount": amt, "percentage": round(percentage, 1)})

    batch_breakdown = []
    for name, amt in batch_dict.items():
        percentage = (amt / total_income * 100) if total_income > 0 else 0
        batch_breakdown.append({"name": name, "amount": amt, "percentage": round(percentage, 1)})

    # Sort breakdowns by amount desc
    course_breakdown.sort(key=lambda x: x["amount"], reverse=True)
    batch_breakdown.sort(key=lambda x: x["amount"], reverse=True)

    return {
        "total_income": total_income,
        "total_expenses": total_expenses,
        "net_profit": net_profit,
        "monthly_data": monthly_data[-6:], # Last 6 months for chart brevity
        "course_breakdown": course_breakdown,
        "batch_breakdown": batch_breakdown
    }
