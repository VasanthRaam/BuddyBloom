import httpx
import time

def test_registration():
    url = "https://buddybloom-dev-981707949514.asia-south1.run.app/api/v1/auth/register"
    timestamp = int(time.time())
    payload = {
        "email": f"test_notif_{timestamp}@example.com",
        "full_name": f"Test Notif User {timestamp}",
        "role": "student",
        "password": "Password123!",
        "phone": "+919876543210"
    }
    
    print(f"[TEST] Sending registration request to Cloud Run: {payload['email']}")
    response = httpx.post(url, json=payload, timeout=15)
    print(f"[TEST] Response Code: {response.status_code}")
    print(f"[TEST] Response Body: {response.text}")

if __name__ == "__main__":
    test_registration()
