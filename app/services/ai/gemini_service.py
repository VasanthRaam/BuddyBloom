import logging
import httpx
from fastapi import HTTPException
import google.generativeai as genai
from app.core.config import settings

logger = logging.getLogger(__name__)

class GeminiService:
    def __init__(self):
        if settings.GEMINI_API_KEY:
            genai.configure(api_key=settings.GEMINI_API_KEY)
            
        self.model_name = "gemini-2.5-flash"
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
        # If OpenAI key is present, route to OpenAI as preferred option / fallback
        if settings.OPENAI_API_KEY:
            return self._generate_openai_response(message, history)

        if not settings.GEMINI_API_KEY:
            raise HTTPException(status_code=500, detail="AI Service is not configured. Please supply a Gemini or OpenAI API Key.")
        
        try:
            model = genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=self.system_prompt
            )
            
            if history:
                formatted_history = []
                for msg in history:
                    role = msg.get("role")
                    if role in ("assistant", "bot", "model"):
                        role = "model"
                    else:
                        role = "user"
                    
                    formatted_history.append({
                        "role": role,
                        "parts": [msg.get("content", "")]
                    })
                
                chat = model.start_chat(history=formatted_history)
                response = chat.send_message(message)
            else:
                response = model.generate_content(message)
                
            return response.text
        except Exception as e:
            err_msg = str(e)
            logger.error(f"Error calling Gemini API: {err_msg}")
            if "prepayment credits" in err_msg.lower() or "billing" in err_msg.lower() or "quota" in err_msg.lower():
                raise HTTPException(
                    status_code=402, 
                    detail="AI Chatbot billing credits or quota are depleted. Please check your Google AI Studio billing status."
                )
            raise HTTPException(status_code=500, detail=f"AI Chatbot error: {err_msg}")

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

def get_gemini_service() -> GeminiService:
    return GeminiService()

