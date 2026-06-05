from fastapi import APIRouter, Depends, HTTPException
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.ai.gemini_service import GeminiService, get_gemini_service

router = APIRouter()

@router.post("/", response_model=ChatResponse)
async def chat_with_tutor(
    request: ChatRequest,
    gemini_service: GeminiService = Depends(get_gemini_service)
):
    """
    Chat with the Hindi Tutor using Gemini.
    """
    try:
        reply = gemini_service.generate_response(request.message)
        return ChatResponse(answer=reply)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
