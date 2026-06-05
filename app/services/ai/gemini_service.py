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

    def generate_response(self, message: str) -> str:
        if not settings.GEMINI_API_KEY:
            raise HTTPException(status_code=500, detail="Gemini API Key not configured")
        
        try:
            model = genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=self.system_prompt
            )
            response = model.generate_content(message)
            return response.text
        except Exception as e:
            logger.error(f"Error calling Gemini API: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to generate response from AI")

def get_gemini_service() -> GeminiService:
    return GeminiService()
