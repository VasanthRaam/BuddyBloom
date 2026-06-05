import logging
from fastapi import HTTPException
import google.generativeai as genai
from app.core.config import settings

logger = logging.getLogger(__name__)

class GeminiService:
    def __init__(self):
        if not settings.GEMINI_API_KEY:
            logger.warning("GEMINI_API_KEY is not set in the environment.")
        else:
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
        if not settings.GEMINI_API_KEY:
            raise HTTPException(status_code=500, detail="Gemini API Key not configured")
        
        try:
            model = genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=self.system_prompt
            )
            
            if history:
                # Format history for Google Gemini SDK. Roles must be 'user' or 'model'.
                formatted_history = []
                for msg in history:
                    role = msg.get("role")
                    # Ensure role is either 'user' or 'model'
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
            logger.error(f"Error calling Gemini API: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to generate response from AI")

def get_gemini_service() -> GeminiService:
    return GeminiService()

