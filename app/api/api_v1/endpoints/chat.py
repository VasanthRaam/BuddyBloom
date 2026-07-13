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
        
        # Check daily prompt limit (max 10 prompts per 24 hours) for non-admin users
        if current_user.get("role") != "admin":
            from datetime import datetime, timedelta, timezone
            from sqlalchemy import func
            
            limit_time = datetime.now(timezone.utc) - timedelta(hours=24)
            
            prompt_count_res = await db.execute(
                select(func.count(ChatMessage.id))
                .where(ChatMessage.user_id == user_uuid)
                .where(ChatMessage.role == "user")
                .where(ChatMessage.created_at >= limit_time)
            )
            prompt_count = prompt_count_res.scalar() or 0
            
            if prompt_count >= 10:
                raise HTTPException(
                    status_code=429,
                    detail="You have reached your daily limit of 10 prompts. Please try again tomorrow."
                )
        
        # 1. Fetch the last 10 messages from the database (filtered by mode)
        result = await db.execute(
            select(ChatMessage)
            .where(ChatMessage.user_id == user_uuid)
            .where(ChatMessage.mode == request.mode)
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
        user_msg = ChatMessage(user_id=user_uuid, role="user", content=request.message, mode=request.mode)
        db.add(user_msg)
        await db.commit()
        
        # 4. Call Gemini service with history and mode
        reply = gemini_service.generate_response(request.message, history=history_list, mode=request.mode)
        
        reply_clean = reply.strip()
        
        if request.mode == "translation":
            # Clean reply of any markdown code blocks
            if reply_clean.startswith("```json"):
                reply_clean = reply_clean[7:]
            elif reply_clean.startswith("```"):
                reply_clean = reply_clean[3:]
            if reply_clean.endswith("```"):
                reply_clean = reply_clean[:-3]
            reply_clean = reply_clean.strip()
 
            # Validate JSON structure, fallback to simple wrapper if invalid
            import json
            try:
                parsed_json = json.loads(reply_clean)
                if not isinstance(parsed_json, dict) or "hindi_script" not in parsed_json:
                    raise ValueError("Missing keys")
            except Exception:
                fallback_obj = {
                    "english": request.message,
                    "hindi_script": reply_clean,
                    "hindi_romanized": ""
                }
                reply_clean = json.dumps(fallback_obj, ensure_ascii=False)
 
        # 5. Save the model reply to the database
        bot_msg = ChatMessage(user_id=user_uuid, role="model", content=reply_clean, mode=request.mode)
        db.add(bot_msg)
        await db.commit()
        
        return ChatResponse(answer=reply_clean)
    except HTTPException as e:
        raise e
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/")
async def get_chat_history(
    mode: str = "general",
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Get the chat history of the current user, filtered by mode.
    """
    try:
        user_uuid = uuid.UUID(current_user["id"])
        result = await db.execute(
            select(ChatMessage)
            .where(ChatMessage.user_id == user_uuid)
            .where(ChatMessage.mode == mode)
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

