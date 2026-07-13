from pydantic import BaseModel

class ChatRequest(BaseModel):
    message: str
    mode: str = "general"

class ChatResponse(BaseModel):
    answer: str
