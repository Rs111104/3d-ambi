import pytest
import json
import os
import bcrypt
import sys

# Set environment variables BEFORE importing server
os.environ["ADMIN_USER"] = "testadmin"
os.environ["ADMIN_PASSWORD_HASH"] = bcrypt.hashpw(b"testpass", bcrypt.gensalt()).decode()
os.environ["FLASK_SECRET"] = "testsecret"
os.environ["DB_PATH"] = "test.db"

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

from server import app
import db

@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setenv("DB_PATH", db_path)
    
    with app.app_context():
        db.init_db()
    
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c

def test_get_question_without_session(client):
    r = client.get("/api/question")
    assert r.status_code == 403

def test_admin_login_wrong_password(client):
    r = client.post("/api/admin/login",
        json={"username": "testadmin", "password": "wrong"},
        headers={"X-Requested-With": "XMLHttpRequest"})
    assert r.status_code == 401

def test_admin_login_correct(client):
    # The module level constants were already set by the os.environ calls above
    r = client.post("/api/admin/login",
        json={"username": "testadmin", "password": "testpass"},
        headers={"X-Requested-With": "XMLHttpRequest"})
    assert r.status_code == 200
    assert "admin_token" in r.headers.get("Set-Cookie", "")

def test_decoy_requires_session(client):
    r = client.get("/api/decoy")
    assert r.status_code == 403

def test_admin_dashboard_requires_auth(client):
    r = client.get("/admin")
    assert r.status_code == 302  # redirect to login

def test_session_start(client):
    r = client.post("/api/session/start", headers={"X-Requested-With": "XMLHttpRequest"})
    assert r.status_code == 200
    data = json.loads(r.data)
    assert "session_id" in data
    assert "session_id" in r.headers.get("Set-Cookie", "")
