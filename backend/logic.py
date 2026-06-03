import json
import random
import time
import uuid
import secrets
import hmac
import hashlib
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from db import db_connect, DB_LOCK, get_setting
from config import Config

EVENT_CONDITION = threading.Condition() if 'threading' in globals() else None
import threading
EVENT_CONDITION = threading.Condition()
LATEST_EVENTS = []

def derive_session_key(token: str) -> bytes:
    """Derives a deterministic 256-bit key for a session using HKDF-like construction."""
    ikm = token.encode("utf-8")
    prk = hmac.new(Config.SESSION_SALT, ikm, hashlib.sha256).digest()
    return hmac.new(prk, b"session-key\x01", hashlib.sha256).digest()

def encrypt_data(data_dict: dict, key_bytes: bytes) -> dict:
    """Encrypts a dictionary using AES-256-GCM."""
    aesgcm = AESGCM(key_bytes)
    nonce = secrets.token_bytes(12)
    data_json = json.dumps(data_dict).encode("utf-8")
    ciphertext = aesgcm.encrypt(nonce, data_json, None)
    return {"ciphertext": ciphertext.hex(), "nonce": nonce.hex()}

def create_session(name: str, set_id: str = None, invite_token: str = None) -> str:
    """Initializes a new assessment session and generates an ephemeral token."""
    token = str(uuid.uuid4())
    session_key = derive_session_key(token).hex()
    
    with DB_LOCK:
        conn = db_connect()
        # Fetch question order (shuffled)
        rows = conn.execute("SELECT id FROM questions").fetchall()
        order = [int(r["id"]) for r in rows]
        random.shuffle(order)
        
        conn.execute(
            "INSERT INTO sessions (token, session_key, question_order_json, created_at) VALUES (?, ?, ?, ?)",
            (token, session_key, json.dumps(order), int(time.time()))
        )
        conn.execute(
            "INSERT INTO session_meta (token, name, started_at) VALUES (?, ?, ?)",
            (token, name, int(time.time()))
        )
        conn.commit(); conn.close()
    return token

def record_answer(token: str, q_id: int, a_idx: int, time_ms: int, compliance: float, proof: str = None) -> tuple:
    """Records a candidate's answer with cryptographic verification of the rendering proof."""
    session = get_session(token)
    if not session: return False, "invalid_session"
    
    # Verify Rendering Proof (HMAC-SHA256)
    if proof:
        key = derive_session_key(token)
        challenge = str(q_id).encode("utf-8")
        expected = hmac.new(key, challenge + str(a_idx).encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(proof, expected):
            record_event(token, "tamper_detected", "Invalid rendering proof")
            return False, "invalid_proof"

    with DB_LOCK:
        conn = db_connect()
        # Simple scoring
        q = conn.execute("SELECT correct_index FROM questions WHERE id = ?", (q_id,)).fetchone()
        correct = 1 if q and int(q["correct_index"]) == int(a_idx) else 0
        
        conn.execute(
            "INSERT INTO session_answers (token, question_id, answer_index, correct, time_ms, head_compliance, created_at) VALUES (?,?,?,?,?,?,?)",
            (token, q_id, a_idx, correct, time_ms, compliance, int(time.time()))
        )
        conn.execute("UPDATE sessions SET answer_received = 1, next_index = next_index + 1 WHERE token = ?", (token,))
        conn.commit(); conn.close()
    return True, "ok"

def record_event(token: str, event_type: str, detail: str = None):
    """Logs a proctoring event and broadcasts it to the real-time admin stream."""
    with DB_LOCK:
        conn = db_connect()
        # Idempotency: skip if identical event logged in last 2 seconds
        recent = conn.execute("SELECT id FROM session_events WHERE token=? AND event_type=? AND created_at > ?", (token, event_type, int(time.time()) - 2)).fetchone()
        if recent: return
        conn.execute("INSERT INTO session_events (token, event_type, detail, created_at) VALUES (?,?,?,?)", (token, event_type, detail, int(time.time())))
        conn.commit(); conn.close()
    
    with EVENT_CONDITION:
        LATEST_EVENTS.append({"token": token, "type": event_type, "detail": detail, "at": int(time.time())})
        if len(LATEST_EVENTS) > 50: LATEST_EVENTS.pop(0)
        EVENT_CONDITION.notify_all()

def get_session(token: str):
    """Retrieves session state from the database."""
    with DB_LOCK:
        conn = db_connect(); r = conn.execute("SELECT * FROM sessions WHERE token = ?", (token,)).fetchone(); conn.close()
        return r
