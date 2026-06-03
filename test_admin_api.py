import requests
BASE_URL = "http://localhost:8080"
r = requests.post(f"{BASE_URL}/api/admin/login", json={'username': 'admin', 'password': 'admin123'})
data = r.json()
headers = {'Authorization': f"Bearer {data['token']}", 'X-CSRF-Token': data['csrfToken']}
r = requests.post(f"{BASE_URL}/api/admin/question", json={'subject': 'Science', 'question': 'What is H2O?', 'options': ['Water', 'Acid', 'Salt', 'Gas'], 'correctIndex': 0, 'decoyLeft': 'Is it blue?', 'decoyRight': 'Is it wet?'}, headers=headers)
print(r.status_code, r.json())
