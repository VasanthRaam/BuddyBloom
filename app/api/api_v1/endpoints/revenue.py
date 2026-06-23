from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case
from typing import List, Any
from uuid import UUID
from collections import defaultdict
import datetime

from app.db.database import get_db
from app.db.models import User, FeePayment, UserRole, Expense, Income, Student, Enrollment, Batch, Course
from app.api.deps import get_current_user
from app.schemas.revenue import ExpenseCreate, ExpenseResponse, IncomeCreate, IncomeResponse, RevenueDashboardData

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

@router.post("/incomes", response_model=IncomeResponse)
async def create_income(
    *,
    db: AsyncSession = Depends(get_db),
    income_in: IncomeCreate,
    current_user: dict = Depends(get_current_user)
) -> Any:
    """
    Create a new manual income. Admin only.
    """
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Not enough permissions")

    student = None
    if income_in.category == "Course Fee":
        if not income_in.student_id:
            raise HTTPException(status_code=400, detail="student_id is required for Course Fee category")
        
        # Resolve student profile
        student_res = await db.execute(
            select(Student).where(Student.user_id == income_in.student_id)
        )
        student = student_res.scalars().first()
        if not student:
            student_res = await db.execute(
                select(Student).where(Student.id == income_in.student_id)
            )
            student = student_res.scalars().first()

        if not student:
            raise HTTPException(status_code=404, detail="Student profile not found")

        # Resolve active enrollment
        enr_res = await db.execute(
            select(Enrollment).where(Enrollment.student_id == student.id).limit(1)
        )
        enrollment = enr_res.scalars().first()
        course_id = None
        batch_id = None
        if enrollment:
            batch_id = enrollment.batch_id
            batch_res = await db.execute(select(Batch).where(Batch.id == batch_id))
            batch = batch_res.scalars().first()
            if batch:
                course_id = batch.course_id

        # Parse income_date to datetime with timezone for FeePayment
        paid_datetime = datetime.datetime.combine(income_in.income_date, datetime.time.min).replace(tzinfo=datetime.timezone.utc)

        # Create FeePayment
        import uuid
        fee = FeePayment(
            id=uuid.uuid4(),
            user_id=student.user_id,
            amount=income_in.amount,
            status="paid",
            due_date=paid_datetime,
            paid_at=paid_datetime,
            course_id=course_id,
            batch_id=batch_id,
            is_manual=True
        )
        db.add(fee)

        # Create In-App Notification for Student
        from app.db.models import Notification
        notif = Notification(
            user_id=student.user_id,
            title="Fee Payment Received",
            message=f"Your fee payment of ₹{income_in.amount} has been successfully received and verified.",
            link_to="Fees"
        )
        db.add(notif)

    income = Income(
        amount=income_in.amount,
        category=income_in.category,
        description=income_in.description,
        income_date=income_in.income_date,
        created_by=UUID(current_user["id"]),
        student_id=income_in.student_id
    )
    db.add(income)
    await db.commit()
    await db.refresh(income)

    # Trigger real-time push notification for student
    if income_in.category == "Course Fee" and student:
        from app.services.notification_service import NotificationService
        try:
            await NotificationService.send_push_notification(
                db,
                student.user_id,
                "Fee Payment Received ✅",
                f"Your fee payment of ₹{income_in.amount} has been successfully received and verified.",
                {"type": "fee_payment", "screen": "Fees"}
            )
        except Exception as e:
            print(f"⚠️ [REVENUE] Failed to send push notification to user {student.user_id}: {e}")

    return income

@router.get("/incomes", response_model=List[IncomeResponse])
async def get_incomes(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
) -> Any:
    """
    Get all manual incomes. Admin only.
    """
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Not enough permissions")

    result = await db.execute(
        select(Income)
        .where(Income.category != "Course Fee")
        .order_by(Income.income_date.desc())
    )
    return result.scalars().all()

@router.get("/dashboard", response_model=RevenueDashboardData)
async def get_revenue_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
) -> Any:
    """
    Get revenue dashboard data. Admin only.

    OPTIMIZED: Previously fired 2-4 DB queries per fee record in a Python loop (N+1 problem).
    Now uses SQL JOINs and GROUP BY to fetch all breakdowns in a handful of queries,
    regardless of how many students or fees exist.
    """
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Not enough permissions")

    # ── 1. Totals: paid fees + manual incomes ─────────────────────────────────
    paid_sum_res = await db.execute(
        select(func.sum(FeePayment.amount)).where(FeePayment.status == "paid")
    )
    paid_fees_total = paid_sum_res.scalar() or 0.0

    manual_sum_res = await db.execute(
        select(func.sum(Income.amount)).where(Income.category != "Course Fee")
    )
    manual_incomes_total = manual_sum_res.scalar() or 0.0

    total_income = paid_fees_total + manual_incomes_total

    expense_sum_res = await db.execute(select(func.sum(Expense.amount)))
    total_expenses = expense_sum_res.scalar() or 0.0

    net_profit = total_income - total_expenses

    # ── 2. Monthly aggregation (single query each for fees, incomes, expenses) ─
    fees_monthly_res = await db.execute(
        select(
            func.to_char(FeePayment.paid_at, "YYYY-MM").label("month"),
            func.sum(FeePayment.amount).label("total"),
        )
        .where(FeePayment.status == "paid", FeePayment.paid_at.isnot(None))
        .group_by("month")
    )
    fees_monthly = {row.month: row.total for row in fees_monthly_res}

    income_monthly_res = await db.execute(
        select(
            func.to_char(Income.income_date, "YYYY-MM").label("month"),
            func.sum(Income.amount).label("total"),
        )
        .where(Income.income_date.isnot(None), Income.category != "Course Fee")
        .group_by("month")
    )
    income_monthly = {row.month: row.total for row in income_monthly_res}

    expense_monthly_res = await db.execute(
        select(
            func.to_char(Expense.expense_date, "YYYY-MM").label("month"),
            func.sum(Expense.amount).label("total"),
        )
        .where(Expense.expense_date.isnot(None))
        .group_by("month")
    )
    expense_monthly = {row.month: row.total for row in expense_monthly_res}

    all_months = sorted(
        set(fees_monthly) | set(income_monthly) | set(expense_monthly)
    )
    monthly_data = [
        {
            "month": m,
            "income": round((fees_monthly.get(m, 0) + income_monthly.get(m, 0)), 1),
            "expense": round(expense_monthly.get(m, 0), 1),
        }
        for m in all_months
    ][-6:]  # Last 6 months

    # ── 3. Course/Batch breakdown via SQL JOIN (replaces the N+1 Python loop) ──
    # Fees that are directly linked to a course/batch (explicit assignment)
    direct_course_res = await db.execute(
        select(
            Course.name.label("course_name"),
            func.sum(FeePayment.amount).label("total"),
        )
        .join(Course, Course.id == FeePayment.course_id)
        .where(FeePayment.status == "paid", FeePayment.course_id.isnot(None))
        .group_by(Course.name)
    )
    course_dict = defaultdict(float)
    for row in direct_course_res:
        course_dict[row.course_name] += row.total

    direct_batch_res = await db.execute(
        select(
            Batch.name.label("batch_name"),
            func.sum(FeePayment.amount).label("total"),
        )
        .join(Batch, Batch.id == FeePayment.batch_id)
        .where(FeePayment.status == "paid", FeePayment.batch_id.isnot(None))
        .group_by(Batch.name)
    )
    batch_dict = defaultdict(float)
    for row in direct_batch_res:
        batch_dict[row.batch_name] += row.total

    # Fallback: historical fees without explicit course/batch → attribute via enrollment
    # Single JOIN query: fee → student → enrollment → batch → course
    fallback_res = await db.execute(
        select(
            Course.name.label("course_name"),
            Batch.name.label("batch_name"),
            func.count(Enrollment.id).label("enr_count"),
            FeePayment.amount.label("fee_amount"),
        )
        .select_from(FeePayment)
        .join(Student, Student.user_id == FeePayment.user_id)
        .join(Enrollment, Enrollment.student_id == Student.id)
        .join(Batch, Batch.id == Enrollment.batch_id)
        .join(Course, Course.id == Batch.course_id)
        .where(
            FeePayment.status == "paid",
            FeePayment.course_id.is_(None),
            FeePayment.batch_id.is_(None),
        )
        .group_by(FeePayment.id, FeePayment.amount, Course.name, Batch.name)
    )
    # We group per fee×enrollment so we can split the fee evenly across enrollments
    fee_enrollment_counts: dict = {}
    fallback_rows = fallback_res.all()
    for row in fallback_rows:
        fee_enrollment_counts.setdefault(row.fee_amount, []).append(
            (row.course_name, row.batch_name, row.enr_count)
        )
    for fee_amount, enrollments in fee_enrollment_counts.items():
        total_enr = sum(e[2] for e in enrollments) or 1
        split = fee_amount / total_enr
        for course_name, batch_name, enr_count in enrollments:
            course_dict[course_name] += split * enr_count
            batch_dict[batch_name] += split * enr_count

    # Manual incomes → attribute to "Manual Income" bucket
    manual_by_cat_res = await db.execute(
        select(Income.category, func.sum(Income.amount).label("total"))
        .where(Income.category != "Course Fee")
        .group_by(Income.category)
    )
    for row in manual_by_cat_res:
        course_dict["Manual Income"] += row.total
        batch_dict[row.category] += row.total

    # ── 4. Format & sort ───────────────────────────────────────────────────────
    def to_breakdown(d: dict) -> list:
        items = []
        for name, amt in d.items():
            pct = (amt / total_income * 100) if total_income > 0 else 0
            items.append({"name": name, "amount": round(amt, 1), "percentage": round(pct, 1)})
        items.sort(key=lambda x: x["amount"], reverse=True)
        return items

    return {
        "total_income": round(total_income, 1),
        "total_expenses": round(total_expenses, 1),
        "net_profit": round(net_profit, 1),
        "monthly_data": monthly_data,
        "course_breakdown": to_breakdown(course_dict),
        "batch_breakdown": to_breakdown(batch_dict),
    }

