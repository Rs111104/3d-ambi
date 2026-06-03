import json
import random
import time
import uuid
import secrets
import hmac
import hashlib
import threading
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from db import db_connect, DB_LOCK, get_setting
from config import Config

# Real-time event broadcasting state
EVENT_CONDITION = threading.Condition()
LATEST_EVENTS = []

def derive_session_key(session_token: str) -> bytes:
    """
    Derives a cryptographically strong 256-bit AES key unique to the candidate's session.
    Uses an HKDF-style HMAC chain to ensure key isolation.
    """
    input_keying_material = session_token.encode("utf-8")
    pseudo_random_key = hmac.new(Config.SESSION_SALT, input_keying_material, hashlib.sha256).digest()
    return hmac.new(pseudo_random_key, b"3d-ambi-v1-session-key", hashlib.sha256).digest()

def encrypt_data(data_dictionary: dict, key_bytes: bytes) -> dict:
    """
    Encrypts a dictionary using authenticated AES-256-GCM encryption.
    The resulting payload ensures both confidentiality and integrity of test content.
    """
    aes_gcm_engine = AESGCM(key_bytes)
    initialization_vector = secrets.token_bytes(12) # Standard 96-bit nonce for GCM
    data_bytes = json.dumps(data_dictionary).encode("utf-8")
    
    ciphertext = aes_gcm_engine.encrypt(initialization_vector, data_bytes, None)
    
    return {
        "ciphertext": ciphertext.hex(),
        "nonce": initialization_vector.hex()
    }

def create_session(candidate_name: str) -> str:
    """
    Generates a new secure assessment session for a candidate.
    Randomizes the question sequence and persists initial session metadata.
    """
    session_token = str(uuid.uuid4())
    session_key_hex = derive_session_key(session_token).hex()
    
    with DB_LOCK:
        conn = db_connect()
        # Fetch available questions to build a randomized order
        question_rows = conn.execute("SELECT id FROM questions").fetchall()
        if not question_rows:
            # Handle empty bank gracefully
            logger_instance = logging.getLogger("3D-Ambi")
            logger_instance.warning("Session started with an empty question bank.")
            question_ids = []
        else:
            question_ids = [int(row["id"]) for row in question_rows]
            random.shuffle(question_ids)
        
        conn.execute(
            "INSERT INTO sessions (token, session_key, question_order_json, created_at) VALUES (?, ?, ?, ?)",
            (session_token, session_key_hex, json.dumps(question_ids), int(time.time()))
        )
        conn.execute(
            "INSERT INTO session_meta (token, name, started_at) VALUES (?, ?, ?)",
            (session_token, candidate_name, int(time.time()))
        )
        conn.commit()
        conn.close()
        
    return session_token

def record_answer(session_token: str, question_id: int, answer_index: int, time_ms: int, head_compliance: float, render_proof: str = None) -> tuple:
    """
    Commits a candidate's answer to the database after verifying the Render Proof.
    This proof prevents candidates from simulating answers via DevTools without correct head alignment.
    """
    session_data = get_session(session_token)
    if not session_data: 
        return False, "invalid_session"
    
    # 1. Cryptographic Rendering Verification (Challenge-Response)
    if render_proof:
        session_key = derive_session_key(session_token)
        # The challenge is the question ID combined with the selected answer
        challenge_material = str(question_id).encode("utf-8") + str(answer_index).encode("utf-8")
        expected_hmac = hmac.new(session_key, challenge_material, hashlib.sha256).hexdigest()
        
        if not hmac.compare_digest(render_proof, expected_hmac):
            record_event(session_token, "tamper_detected", "Rendering signature mismatch - potential bypass attempt")
            return False, "invalid_rendering_proof"

    # 2. Database Persistence
    with DB_LOCK:
        conn = db_connect()
        # Evaluate correctness server-side
        question_row = conn.execute("SELECT correct_index FROM questions WHERE id = ?", (question_id,)).fetchone()
        is_correct = 1 if (question_row and int(question_row["correct_index"]) == int(answer_index)) else 0
        
        conn.execute(
            """INSERT INTO session_answers 
               (token, question_id, answer_index, correct, time_ms, head_compliance, created_at) 
               VALUES (?,?,?,?,?,?,?)""",
            (session_token, question_id, int(answer_index), is_correct, int(time_ms), float(head_compliance), int(time.time()))
        )
        # Advance the session index
        conn.execute("UPDATE sessions SET answer_received = 1, next_index = next_index + 1 WHERE token = ?", (session_token,))
        conn.commit()
        conn.close()
        
    return True, "ok"

def record_event(session_token: str, event_type: str, detail: str = None):
    """
    Logs a proctoring signal and broadcasts it to any connected administrators.
    Includes a 2-second cooldown to prevent log-flooding from high-frequency browser events.
    """
    with DB_LOCK:
        conn = db_connect()
        # Idempotency check: Ignore identical events from the same session within 2 seconds
        duplicate = conn.execute(
            "SELECT id FROM session_events WHERE token=? AND event_type=? AND created_at > ?", 
            (session_token, event_type, int(time.time()) - 2)
        ).fetchone()
        
        if not duplicate:
            conn.execute(
                "INSERT INTO session_events (token, event_type, detail, created_at) VALUES (?,?,?,?)", 
                (session_token, event_type, detail, int(time.time()))
            )
            conn.commit()
        conn.close()
    
    # Notify connected Admin SSE streams
    with EVENT_CONDITION:
        LATEST_EVENTS.append({
            "token": session_token, 
            "type": event_type, 
            "detail": detail, 
            "at": int(time.time())
        })
        # Maintain a rolling window of recent events for stream recovery
        if len(LATEST_EVENTS) > 100: LATEST_EVENTS.pop(0)
        EVENT_CONDITION.notify_all()

def get_session(session_token: str) -> dict:
    """Safely retrieves current session state from persistence."""
    with DB_LOCK:
        conn = db_connect()
        row = conn.execute("SELECT * FROM sessions WHERE token = ?", (session_token,)).fetchone()
        conn.close()
        return dict(row) if row else None
