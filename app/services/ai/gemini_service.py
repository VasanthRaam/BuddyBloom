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
        
        self.general_prompt = """You are Academy AI Teacher.

You help students learn Hindi, Bharatanatyam, Keyboard, Drawing, and academic subjects.

Use simple language suitable for children.

Do not generate harmful or unrelated content.

If a question is outside academy learning, politely redirect the student."""

        self.translation_prompt = """You are Academy AI Teacher.

Your primary task is to translate any phrase or question the user asks into Hindi.

For every input message, you must return a valid JSON object with the following keys, and absolutely no other text, markdown formatting (do not wrap in ```json ... ```), or conversational filler:
{
  "english": "...",
  "hindi_script": "...",
  "hindi_romanized": "..."
}

Definitions of the fields:
- "english": The input phrase in standardized/corrected English.
- "hindi_script": The Hindi translation in Devanagari script.
- "hindi_romanized": The Hindi translation transliterated into English script (Roman script, e.g. "Aapka naam kya hai?").

If the input is already in Hindi script, provide:
- "english": The English translation.
- "hindi_script": The input Hindi script.
- "hindi_romanized": The transliteration of the Hindi script.

Ensure the JSON is strictly valid. Do not include markdown code block formatting."""

    def generate_response(self, message: str, history: list = None, mode: str = "general") -> str:
        # Prioritize Gemini if GEMINI_API_KEY is configured
        if settings.GEMINI_API_KEY:
            try:
                return self._generate_gemini_response(message, history, mode)
            except Exception as e:
                # If Gemini fails and OpenAI is configured, fall back to OpenAI
                if settings.OPENAI_API_KEY:
                    logger.warning(f"Gemini failed, falling back to OpenAI: {e}")
                    try:
                        return self._generate_openai_response(message, history, mode)
                    except Exception as openai_err:
                        raise openai_err
                raise e
        elif settings.OPENAI_API_KEY:
            return self._generate_openai_response(message, history, mode)
        else:
            raise HTTPException(status_code=500, detail="AI Service is not configured. Please supply a Gemini or OpenAI API Key.")

    def _generate_gemini_response(self, message: str, history: list = None, mode: str = "general") -> str:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={settings.GEMINI_API_KEY}"
        
        contents = []
        if history:
            for msg in history:
                role = msg.get("role")
                if role in ("assistant", "bot", "model"):
                    role = "model"
                else:
                    role = "user"
                contents.append({
                    "role": role,
                    "parts": [{"text": msg.get("content", "")}]
                })
        
        contents.append({
            "role": "user",
            "parts": [{"text": message}]
        })
        
        prompt = self.translation_prompt if mode == "translation" else self.general_prompt
        payload = {
            "contents": contents,
            "systemInstruction": {
                "parts": [{"text": prompt}]
            }
        }
        
        try:
            resp = httpx.post(url, json=payload, timeout=30.0)
            if resp.status_code != 200:
                err_text = resp.text
                logger.error(f"Gemini API returned error code {resp.status_code}: {err_text}")
                if "prepayment credits" in err_text.lower() or "billing" in err_text.lower() or "quota" in err_text.lower():
                    raise HTTPException(
                        status_code=402, 
                        detail="AI Chatbot billing credits or quota are depleted. Please check your Google AI Studio billing status."
                    )
                raise HTTPException(status_code=resp.status_code, detail=f"Gemini error: {err_text}")
                
            data = resp.json()
            try:
                reply = data["candidates"][0]["content"]["parts"][0]["text"]
                return reply
            except (KeyError, IndexError) as parse_err:
                logger.error(f"Failed to parse Gemini response structure: {data}. Error: {parse_err}")
                raise HTTPException(status_code=500, detail=f"Failed to parse Gemini response: {data}")
        except HTTPException as e:
            raise e
        except Exception as e:
            logger.error(f"Failed direct Gemini call: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to generate response from Gemini: {str(e)}")

    def _generate_openai_response(self, message: str, history: list = None, mode: str = "general") -> str:
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        
        # Build messages payload for OpenAI
        prompt = self.translation_prompt if mode == "translation" else self.general_prompt
        messages = [{"role": "system", "content": prompt}]
        
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

