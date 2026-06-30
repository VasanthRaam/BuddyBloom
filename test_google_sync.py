import httpx

def main():
    url = "https://buddybloom.onrender.com/api/v1/auth/google-sync"
    payload = {
        "access_token": "mock_token",
        "email": "vasanthraam89@gmail.com",
        "full_name": "Vasanth Raam"
    }
    print(f"Sending POST to {url}...")
    try:
        resp = httpx.post(url, json=payload, timeout=20.0)
        print(f"Status Code: {resp.status_code}")
        print("Response Content:")
        print(resp.text)
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    main()
