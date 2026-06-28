from fastapi import APIRouter, HTTPException, Depends, status, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.db.database import get_db
from app.db.models import Lead, Notification, User, UserRole
import uuid

router = APIRouter()

class EnquiryCreate(BaseModel):
    firstName: str
    lastName: str
    phone: str
    course: str
    batch: str  # "trichy" | "vaiyampatti"
    message: str | None = None

async def notify_admins(lead_id: uuid.UUID, first_name: str, last_name: str, course: str):
    from app.db.database import AsyncSessionLocal
    from app.services.notification_service import NotificationService
    
    full_name = f"{first_name} {last_name}"
    lead_id_str = str(lead_id)
    
    async with AsyncSessionLocal() as session:
        # Find all administrators
        admin_res = await session.execute(select(User).where(User.role == UserRole.admin))
        admins = admin_res.scalars().all()
        
        for admin in admins:
            # 1. Create real-time notification in DB
            notif = Notification(
                id=uuid.uuid4(),
                user_id=admin.id,
                title="New Website Enquiry 📬",
                message=f"{full_name} sent an enquiry for the {course} course.",
                link_to=f"Enquiry:{lead_id_str}",
                is_read=False,
            )
            session.add(notif)
            
            # 2. Trigger push notification
            await NotificationService.send_push_notification(
                session, 
                admin.id, 
                "New Website Enquiry 📬",
                f"{full_name} is interested in {course}.",
                {"type": "enquiry", "id": lead_id_str}
            )
            
        await session.commit()

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_enquiry(
    request: EnquiryCreate, 
    background_tasks: BackgroundTasks, 
    db: AsyncSession = Depends(get_db)
):
    # Store lead details in database
    lead = Lead(
        id=uuid.uuid4(),
        first_name=request.firstName,
        last_name=request.lastName,
        phone=request.phone,
        course=request.course,
        batch=request.batch,
        message=request.message
    )
    db.add(lead)
    await db.commit()
    
    # Run notification triggering in the background so request finishes instantly
    background_tasks.add_task(
        notify_admins, 
        lead.id, 
        request.firstName, 
        request.lastName, 
        request.course
    )
    
    return {
        "message": "Enquiry submitted successfully.",
        "lead_id": str(lead.id)
    }

@router.get("/")
async def get_all_enquiries(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Lead).order_by(Lead.created_at.desc()))
    leads = result.scalars().all()
    return [
        {
            "id": str(l.id),
            "firstName": l.first_name,
            "lastName": l.last_name,
            "phone": l.phone,
            "course": l.course,
            "batch": l.batch,
            "message": l.message,
            "created_at": l.created_at.isoformat() if l.created_at else None
        } for l in leads
    ]
