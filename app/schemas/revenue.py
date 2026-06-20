from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID
from datetime import date, datetime

class ExpenseCreate(BaseModel):
    amount: float
    category: str
    description: Optional[str] = None
    expense_date: date

class ExpenseResponse(BaseModel):
    id: UUID
    amount: float
    category: str
    description: Optional[str]
    expense_date: date
    created_at: datetime
    created_by: Optional[UUID]

    class Config:
        from_attributes = True

class IncomeCreate(BaseModel):
    amount: float
    category: str
    description: Optional[str] = None
    income_date: date

class IncomeResponse(BaseModel):
    id: UUID
    amount: float
    category: str
    description: Optional[str]
    income_date: date
    created_at: datetime
    created_by: Optional[UUID]

    class Config:
        from_attributes = True

class MonthlyData(BaseModel):
    month: str
    income: float
    expense: float

class BreakdownItem(BaseModel):
    name: str
    amount: float
    percentage: float

class RevenueDashboardData(BaseModel):
    total_income: float
    total_expenses: float
    net_profit: float
    monthly_data: List[MonthlyData]
    course_breakdown: List[BreakdownItem]
    batch_breakdown: List[BreakdownItem]
