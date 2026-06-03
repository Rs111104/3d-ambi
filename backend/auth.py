import hashlib
import os
import hmac
import time
import uuid
from db import db_connect, DB_LOCK
from config import Config

def hash_password(password: str, salt: str = None) -> tuple:
    """Derives a secure PBKDF2-SHA256 hash for a password."""
    if salt is None: salt = os.urandom(16)
    if isinstance(salt, str): salt = bytes.fromhex(salt)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200000)
    return digest.hex(), salt.hex()

def verify_admin_token(token: str) -> bool:
    """Validates an admin session token and checks for expiration."""
    with DB_LOCK:
        conn = db_connect()
        row = conn.execute("SELECT expires_at FROM admin_sessions WHERE token = ?", (token,)).fetchone()
        if not row: return False
        if row["expires_at"] < time.time():
            conn.execute("DELETE FROM admin_sessions WHERE token = ?", (token,)); conn.commit()
            return False
        return True

def issue_admin_token(username: str) -> tuple:
    """Creates a new admin session and associated CSRF token."""
    token = uuid.uuid4().hex
    csrf = os.urandom(32).hex()
    expiry = time.time() + Config.TOKEN_TTL_SEC
    with DB_LOCK:
        conn = db_connect()
        conn.execute("INSERT INTO admin_sessions (token, username, expires_at, csrf_token) VALUES (?,?,?,?)", (token, username, expiry, csrf))
        conn.commit(); conn.close()
    return token, csrf

def verify_csrf_token(token: str, csrf: str) -> bool:
    """Protects against Cross-Site Request Forgery via stateful token comparison."""
    with DB_LOCK:
        conn = db_connect()
        row = conn.execute("SELECT csrf_token FROM admin_sessions WHERE token = ?", (token,)).fetchone()
        if not row: return False
        return hmac.compare_digest(row["csrf_token"], csrf)

def authenticate_admin(username: str, password: str) -> tuple:
    """Verifies credentials and returns a session tuple on success."""
    with DB_LOCK:
        conn = db_connect()
        user = conn.execute("SELECT password_hash, salt FROM admin_users WHERE username = ?", (username,)).fetchone()
        if not user: return None
        h, _ = hash_password(password, user["salt"])
        if hmac.compare_digest(h, user["password_hash"]):
            return issue_admin_token(username)
        return None
