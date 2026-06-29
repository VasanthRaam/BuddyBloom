import google.generativeai as genai
from app.core.config import settings

def main():
    try:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        print("Listing models...")
        for m in genai.list_models():
            print(f"Name: {m.name}, Supported Actions: {m.supported_generation_methods}")
    except Exception as e:
        print("Error listing models:", e)

if __name__ == "__main__":
    main()
