import asyncio
from app.services.ai.gemini_service import GeminiService

async def main():
    service = GeminiService()
    print("Testing the updated GeminiService.generate_response direct REST API client...")
    try:
        reply = service.generate_response("Say hello in Hindi")
        print("\nSuccess! Response:")
        print(reply)
    except Exception as e:
        print("\nFailed:", e)

if __name__ == "__main__":
    asyncio.run(main())
