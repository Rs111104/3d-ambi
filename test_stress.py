import requests
import json
import hmac
import hashlib

BASE_URL = "http://localhost:8080"

def derive_session_key(session_token):
    # Matches backend logic.py
    salt = b"3d-ambi-v1"
    input_keying_material = session_token.encode("utf-8")
    pseudo_random_key = hmac.new(salt, input_keying_material, hashlib.sha256).digest()
    return hmac.new(pseudo_random_key, b"3d-ambi-v1-session-key", hashlib.sha256).digest()

def generate_proof(session_token, question_id, answer_index):
    key = derive_session_key(session_token)
    challenge = str(question_id).encode("utf-8") + str(answer_index).encode("utf-8")
    return hmac.new(key, challenge, hashlib.sha256).hexdigest()

def test_stress():
    print("--- Stress Test Starting ---")
    
    # 1. Start session
    r = requests.post(f"{BASE_URL}/api/session/start", json={"name": "Stress Tester"})
    session_token = r.json()["sessionToken"]
    print(f"Session started: {session_token}")

    # 2. Get question
    r = requests.post(f"{BASE_URL}/api/session/next", json={"sessionToken": session_token})
    q_data = r.json()
    q_id = q_data["questionId"]
    print(f"Got question {q_id}")

    # 3. Test Correct Submission
    proof = generate_proof(session_token, q_id, 0)
    payload = {
        "sessionToken": session_token,
        "questionId": q_id,
        "answerIndex": 0,
        "timeMs": 1000,
        "headCompliance": 1.0,
        "proof": proof
    }
    r = requests.post(f"{BASE_URL}/api/session/answer", json=payload)
    print(f"Correct submission status: {r.status_code} - {r.json()}")

    # 4. Test Duplicate Submission
    r = requests.post(f"{BASE_URL}/api/session/answer", json=payload)
    print(f"Duplicate submission status: {r.status_code} - {r.json()}")

    # 5. Test Tamper (Invalid Proof)
    r = requests.post(f"{BASE_URL}/api/session/answer", json={**payload, "proof": "wrong_proof"})
    print(f"Tamper submission status: {r.status_code} - {r.json()}")

    # 6. Test Invalid Session
    r = requests.post(f"{BASE_URL}/api/session/answer", json={**payload, "sessionToken": "invalid_token"})
    print(f"Invalid session status: {r.status_code} - {r.json()}")

    # 7. Admin Check
    r = requests.post(f"{BASE_URL}/api/admin/login", json={"username": "admin", "password": "admin123"})
    admin_token = r.json()["token"]
    r = requests.get(f"{BASE_URL}/api/admin/session/{session_token}", headers={"Authorization": f"Bearer {admin_token}"})
    events = r.json()["events"]
    print(f"Recorded events for session: {[e['event_type'] for e in events]}")

if __name__ == "__main__":
    test_stress()
