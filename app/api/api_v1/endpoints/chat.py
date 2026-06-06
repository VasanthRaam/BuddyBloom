from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.db.database import get_db
from app.db.models import ChatMessage
from app.api.deps import get_current_user
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.ai.gemini_service import GeminiService, get_gemini_service
import uuid

router = APIRouter()

@router.post("/", response_model=ChatResponse)
async def chat_with_tutor(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    gemini_service: GeminiService = Depends(get_gemini_service)
):
    """
    Chat with the Hindi Tutor using Gemini, preserving context memory.
    """
    try:
        user_uuid = uuid.UUID(current_user["id"])
        
        # 1. Fetch the last 10 messages from the database
        result = await db.execute(
            select(ChatMessage)
            .where(ChatMessage.user_id == user_uuid)
            .order_by(ChatMessage.created_at.desc())
            .limit(10)
        )
        history_msgs = result.scalars().all()
        # Reverse them to get chronological order (oldest first)
        history_msgs.reverse()
        
        # 2. Format history for the Gemini service
        history_list = [
            {"role": msg.role, "content": msg.content}
            for msg in history_msgs
        ]
        
        # 3. Save the user message to the database first, so it gets an earlier created_at timestamp
        user_msg = ChatMessage(user_id=user_uuid, role="user", content=request.message)
        db.add(user_msg)
        await db.commit()
        
        # 4. Call Gemini service with history
        reply = gemini_service.generate_response(request.message, history=history_list)
        
        # 5. Save the model reply to the database
        bot_msg = ChatMessage(user_id=user_uuid, role="model", content=reply)
        db.add(bot_msg)
        await db.commit()
        
        return ChatResponse(answer=reply)
    except HTTPException as e:
        raise e
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/")
async def get_chat_history(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Get the chat history of the current user.
    """
    try:
        user_uuid = uuid.UUID(current_user["id"])
        result = await db.execute(
            select(ChatMessage)
            .where(ChatMessage.user_id == user_uuid)
            .order_by(ChatMessage.created_at.asc())
            .limit(50)
        )
        history_msgs = result.scalars().all()
        return [
            {
                "id": str(msg.id),
                "role": msg.role,
                "content": msg.content,
                "created_at": msg.created_at
            }
            for msg in history_msgs
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

