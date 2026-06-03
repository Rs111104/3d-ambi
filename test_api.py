import requests
import json

BASE_URL = "http://localhost:8080"

def test_api():
    print("Testing /api/admin/login...")
    payload = {"username": "admin", "password": "admin123"}
    r = requests.post(f"{BASE_URL}/api/admin/login", json=payload)
    print(f"Status: {r.status_code}")
    print(f"Response: {r.text}")
    if r.status_code != 200:
        return

    data = r.json()
    token = data["token"]
    csrf = data["csrfToken"]
    headers = {"Authorization": f"Bearer {token}", "X-CSRF-Token": csrf}

    print("\nTesting /api/session/start...")
    r = requests.post(f"{BASE_URL}/api/session/start", json={"name": "Test Candidate"})
    print(f"Status: {r.status_code}")
    session_token = r.json()["sessionToken"]
    print(f"Session Token: {session_token}")

    print("\nTesting /api/session/next...")
    r = requests.post(f"{BASE_URL}/api/session/next", json={"sessionToken": session_token})
    print(f"Status: {r.status_code}")
    print(f"Response: {r.text[:200]}...")

    print("\nTesting /api/admin/sessions...")
    r = requests.get(f"{BASE_URL}/api/admin/sessions", headers=headers)
    print(f"Status: {r.status_code}")
    print(f"Sessions count: {len(r.json())}")

if __name__ == "__main__":
    test_api()
