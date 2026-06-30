import asyncio
from app.services.ai.gemini_service import GeminiService

async def main():
    service = GeminiService()
    print("Sending message to OpenAI via GeminiService...")
    try:
        reply = service.generate_response("Translate 'Good morning teacher' to Hindi.")
        print("\nSuccess! AI Response:")
        print(reply)
    except Exception as e:
        print("\nFailed calling AI Service:", e)

if __name__ == "__main__":
    asyncio.run(main())
