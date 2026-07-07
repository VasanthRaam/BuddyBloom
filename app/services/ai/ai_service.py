import logging
import httpx
from fastapi import HTTPException
from app.core.config import settings

logger = logging.getLogger(__name__)

class AIService:
    def __init__(self):
        self.system_prompt = """You are Academy AI Teacher.

You help students learn Hindi, Bharatanatyam, Keyboard, Drawing, and academic subjects.

For Hindi translation questions:

Return:

1. Transliteration
2. Hindi script
3. English meaning

Format:

Transliteration:
...

Hindi:
...

Meaning:
...

Use simple language suitable for children.

Do not generate harmful or unrelated content.

If a question is outside academy learning, politely redirect the student."""

    def generate_response(self, message: str, history: list = None) -> str:
        if settings.OPENAI_API_KEY:
            return self._generate_openai_response(message, history)
        else:
            raise HTTPException(
                status_code=500, 
                detail="AI Service is not configured. Please supply an OpenAI API Key."
            )

    def _generate_openai_response(self, message: str, history: list = None) -> str:
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        
        # Build messages payload for OpenAI
        messages = [{"role": "system", "content": self.system_prompt}]
        
        if history:
            for msg in history:
                role = msg.get("role")
                if role in ("model", "bot", "assistant"):
                    role = "assistant"
                else:
                    role = "user"
                messages.append({"role": role, "content": msg.get("content", "")})
                
        messages.append({"role": "user", "content": message})
        
        payload = {
            "model": "gpt-4o-mini",
            "messages": messages,
            "temperature": 0.7
        }
        
        try:
            resp = httpx.post(url, headers=headers, json=payload, timeout=30.0)
            if resp.status_code != 200:
                logger.error(f"OpenAI API returned error: {resp.text}")
                raise HTTPException(status_code=resp.status_code, detail=f"OpenAI error: {resp.text}")
                
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"Failed calling OpenAI API: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to generate response from OpenAI: {str(e)}")

def get_ai_service() -> AIService:
    return AIService()
