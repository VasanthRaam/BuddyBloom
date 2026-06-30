import httpx
from app.core.config import settings

def main():
    api_key = settings.GEMINI_API_KEY
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": "Say hello in Hindi"}]
            }
        ],
        "systemInstruction": {
            "parts": [{"text": "You are a friendly tutor."}]
        }
    }
    
    print(f"Calling Gemini direct URL: https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=...")
    try:
        resp = httpx.post(url, json=payload, timeout=20.0)
        print("Status Code:", resp.status_code)
        print("Response headers:")
        print(dict(resp.headers))
        print("\nResponse Body:")
        print(resp.text)
    except Exception as e:
        print("Failed direct call:", e)

if __name__ == "__main__":
    main()
