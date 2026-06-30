import httpx

def main():
    url = "https://buddybloom.onrender.com/api/v1/diagnostics/ping"
    print(f"Pinging Render backend: {url}...")
    try:
        resp = httpx.get(url, timeout=30.0)
        print(f"Status Code: {resp.status_code}")
        print("Response Content:")
        print(resp.text)
    except Exception as e:
        print("Error pinging Render backend:", e)

if __name__ == "__main__":
    main()
