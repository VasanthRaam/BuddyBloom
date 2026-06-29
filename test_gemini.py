import google.generativeai as genai
from app.core.config import settings

def main():
    print(f"API Key: {settings.GEMINI_API_KEY[:10]}... (len={len(settings.GEMINI_API_KEY)})")
    
    # Try gemini-2.5-flash
    model_name = "gemini-2.5-flash"
    print(f"Attempting to call Gemini API with model: {model_name}...")
    try:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel(model_name=model_name)
        resp = model.generate_content("Say hello in Hindi")
        print("Success! Response:", resp.text)
        return
    except Exception as e:
        print(f"Failed with {model_name}: {e}")
        
    # Try gemini-1.5-flash
    model_name = "gemini-1.5-flash"
    print(f"\nAttempting fallback model: {model_name}...")
    try:
        model = genai.GenerativeModel(model_name=model_name)
        resp = model.generate_content("Say hello in Hindi")
        print("Success! Response:", resp.text)
    except Exception as e:
        print(f"Failed with {model_name}: {e}")

if __name__ == "__main__":
    main()
