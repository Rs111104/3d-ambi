import json
import os
import random
import sqlite3
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import Request, urlopen
import base64
import hashlib
import hmac
import secrets


DB_PATH = os.path.join(os.path.dirname(__file__), "data.db")
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8080"))
LLM_API_KEY = os.environ.get("LLM_API_KEY", "").strip()
LLM_API_URL = os.environ.get("LLM_API_URL", "https://api.openai.com/v1/chat/completions")
LLM_MODEL = os.environ.get("LLM_MODEL", "gpt-4o-mini")
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123!")

SEED_QUESTIONS = [
    {
        "subject": "numerical",
        "difficulty": "medium",
        "question": "A factory produces 240 units in 6 hours. At the same rate, how many units in 9 hours?",
        "options": ["300", "320", "360", "400"],
        "correct": 2
    },
    {
        "subject": "numerical",
        "difficulty": "easy",
        "question": "If 3 workers finish a job in 12 days, how many days for 4 workers at the same rate?",
        "options": ["8", "9", "10", "12"],
        "correct": 1
    },
    {
        "subject": "numerical",
        "difficulty": "medium",
        "question": "A car travels 150 km in 2.5 hours. What is its average speed?",
        "options": ["50 km/h", "55 km/h", "60 km/h", "65 km/h"],
        "correct": 2
    },
    {
        "subject": "numerical",
        "difficulty": "medium",
        "question": "A tank is 3/5 full. After adding 24 liters, it is 4/5 full. What is the tank capacity?",
        "options": ["60 L", "90 L", "120 L", "150 L"],
        "correct": 2
    },
    {
        "subject": "numerical",
        "difficulty": "easy",
        "question": "If a price is reduced by 20% to $80, what was the original price?",
        "options": ["$90", "$95", "$100", "$120"],
        "correct": 2
    },
    {
        "subject": "numerical",
        "difficulty": "hard",
        "question": "A train covers 300 km at 60 km/h and returns at 75 km/h. What is the average speed for the round trip?",
        "options": ["66.7 km/h", "67.5 km/h", "68.6 km/h", "70 km/h"],
        "correct": 0
    },
    {
        "subject": "numerical",
        "difficulty": "medium",
        "question": "If x + y = 20 and x - y = 4, what is the value of x?",
        "options": ["8", "10", "12", "14"],
        "correct": 2
    },
    {
        "subject": "numerical",
        "difficulty": "medium",
        "question": "An item marked $500 is sold at a 15% discount. What is the sale price?",
        "options": ["$425", "$435", "$450", "$475"],
        "correct": 2
    },
    {
        "subject": "numerical",
        "difficulty": "medium",
        "question": "If 5 machines make 200 parts in 8 hours, how many parts can 3 machines make in 10 hours?",
        "options": ["120", "150", "160", "180"],
        "correct": 1
    },
    {
        "subject": "numerical",
        "difficulty": "easy",
        "question": "A person saves 25% of a $2,000 salary. How much is saved?",
        "options": ["$400", "$450", "$500", "$550"],
        "correct": 2
    },
    {
        "subject": "logic",
        "difficulty": "medium",
        "question": "All managers are trained. Some trained staff are remote. Which statement must be true?",
        "options": ["Some managers are remote", "All remote staff are managers", "Some trained staff may be remote", "No managers are remote"],
        "correct": 2
    },
    {
        "subject": "logic",
        "difficulty": "easy",
        "question": "If it rains, the match is canceled. The match is not canceled. What follows?",
        "options": ["It rained", "It did not rain", "The stadium is closed", "Nothing can be concluded"],
        "correct": 1
    },
    {
        "subject": "logic",
        "difficulty": "medium",
        "question": "No cats are dogs. Some pets are cats. What must be true?",
        "options": ["Some pets are not dogs", "All pets are dogs", "Some dogs are pets", "No pets are dogs"],
        "correct": 0
    },
    {
        "subject": "logic",
        "difficulty": "hard",
        "question": "If A implies B and B implies C, and A is true, what must be true?",
        "options": ["B is false", "C is true", "C is false", "A is false"],
        "correct": 1
    },
    {
        "subject": "logic",
        "difficulty": "medium",
        "question": "All engineers are logical. Some logical people are artists. Which statement is valid?",
        "options": ["Some engineers may be artists", "All artists are engineers", "No engineers are artists", "All logical people are engineers"],
        "correct": 0
    }
]

CREATE_SCHEMA = """
CREATE TABLE IF NOT EXISTS questions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  subject TEXT NOT NULL,
  difficulty TEXT NOT NULL,
  question_text TEXT NOT NULL,
  options_json TEXT NOT NULL,
  correct_index INTEGER NOT NULL,
  decoy_left_text TEXT NOT NULL,
  decoy_left_options_json TEXT NOT NULL,
  decoy_right_text TEXT NOT NULL,
  decoy_right_options_json TEXT NOT NULL,
  created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  token TEXT NOT NULL UNIQUE,
  next_index INTEGER NOT NULL,
    session_key TEXT NOT NULL,
  created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS session_meta (
    token TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    started_at INTEGER NOT NULL,
    completed_at INTEGER
);

CREATE TABLE IF NOT EXISTS session_answers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token TEXT NOT NULL,
    question_id INTEGER NOT NULL,
    answer_index INTEGER NOT NULL,
    correct INTEGER NOT NULL,
    time_ms INTEGER NOT NULL,
    head_compliance REAL NOT NULL,
    created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS session_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token TEXT NOT NULL,
    event_type TEXT NOT NULL,
    detail TEXT,
    created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS session_reviews (
    token TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    updated_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS admin_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    salt TEXT NOT NULL,
    created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

DB_LOCK = threading.Lock()
ADMIN_TOKENS = {}
ADMIN_TOKEN_TTL = 8 * 60 * 60
RATE_LIMIT = {}
RATE_LIMIT_WINDOW = 60
RATE_LIMIT_MAX = 120


def db_connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with DB_LOCK:
        conn = db_connect()
        try:
            conn.executescript(CREATE_SCHEMA)
            try:
                conn.execute("ALTER TABLE sessions ADD COLUMN session_key TEXT NOT NULL DEFAULT ''")
            except sqlite3.OperationalError:
                pass
            conn.commit()
        finally:
            conn.close()
    ensure_admin_user()
    ensure_default_settings()


def hash_password(password, salt=None):
    if salt is None:
        salt = os.urandom(16)
    if isinstance(salt, str):
        salt = bytes.fromhex(salt)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200000)
    return digest.hex(), salt.hex()


def ensure_admin_user():
    with DB_LOCK:
        conn = db_connect()
        try:
            row = conn.execute("SELECT id FROM admin_users WHERE username = ?", (ADMIN_USER,)).fetchone()
            if row:
                return
            pw_hash, salt = hash_password(ADMIN_PASSWORD)
            conn.execute(
                "INSERT INTO admin_users (username, password_hash, salt, created_at) VALUES (?, ?, ?, ?)",
                (ADMIN_USER, pw_hash, salt, int(time.time()))
            )
            conn.commit()
        finally:
            conn.close()


def ensure_default_settings():
    defaults = {
        "time_limit": "20",
        "passing_threshold": "0.7",
        "auto_flag_events": json.dumps(["devtools_open", "tab_hidden", "window_blur", "right_click"]),
        "head_compliance_threshold": "0.6"
    }
    with DB_LOCK:
        conn = db_connect()
        try:
            for key, value in defaults.items():
                row = conn.execute("SELECT key FROM settings WHERE key = ?", (key,)).fetchone()
                if not row:
                    conn.execute("INSERT INTO settings (key, value) VALUES (?, ?)", (key, value))
            conn.commit()
        finally:
            conn.close()


def get_setting(key, default=None):
    with DB_LOCK:
        conn = db_connect()
        try:
            row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
            if row:
                return row["value"]
            return default
        finally:
            conn.close()


def set_setting(key, value):
    with DB_LOCK:
        conn = db_connect()
        try:
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
            conn.commit()
        finally:
            conn.close()


def issue_admin_token(username):
    token = uuid.uuid4().hex
    ADMIN_TOKENS[token] = {"user": username, "expires": time.time() + ADMIN_TOKEN_TTL}
    return token


def verify_admin_token(token):
    info = ADMIN_TOKENS.get(token)
    if not info:
        return False
    if info["expires"] < time.time():
        ADMIN_TOKENS.pop(token, None)
        return False
    return True


def fetch_question_count():
    with DB_LOCK:
        conn = db_connect()
        try:
            cur = conn.execute("SELECT COUNT(*) AS count FROM questions")
            return int(cur.fetchone()["count"])
        finally:
            conn.close()


def insert_question(payload):
    with DB_LOCK:
        conn = db_connect()
        try:
            conn.execute(
                """
                INSERT INTO questions (
                    subject, difficulty, question_text, options_json, correct_index,
                    decoy_left_text, decoy_left_options_json,
                    decoy_right_text, decoy_right_options_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["subject"],
                    payload["difficulty"],
                    payload["question"],
                    json.dumps(payload["options"]),
                    payload["correct"],
                    payload["decoy_left"]["question"],
                    json.dumps(payload["decoy_left"]["options"]),
                    payload["decoy_right"]["question"],
                    json.dumps(payload["decoy_right"]["options"]),
                    int(time.time())
                )
            )
            conn.commit()
        finally:
            conn.close()


def insert_session_meta(token, name):
    with DB_LOCK:
        conn = db_connect()
        try:
            row = conn.execute("SELECT token FROM session_meta WHERE token = ?", (token,)).fetchone()
            if row:
                return
            conn.execute(
                "INSERT INTO session_meta (token, name, started_at) VALUES (?, ?, ?)",
                (token, name, int(time.time()))
            )
            conn.commit()
        finally:
            conn.close()


def create_session(name):
    token = str(uuid.uuid4())
    session_key = secrets.token_bytes(32).hex()
    with DB_LOCK:
        conn = db_connect()
        try:
            conn.execute(
                "INSERT INTO sessions (token, next_index, session_key, created_at) VALUES (?, ?, ?, ?)",
                (token, 0, session_key, int(time.time()))
            )
            conn.commit()
        finally:
            conn.close()
    insert_session_meta(token, name)
    return token, session_key


def get_or_create_session(token):
    with DB_LOCK:
        conn = db_connect()
        try:
            if token:
                row = conn.execute("SELECT token, next_index, session_key FROM sessions WHERE token = ?", (token,)).fetchone()
                if row:
                    return row["token"], row["next_index"], row["session_key"]
            token = str(uuid.uuid4())
            session_key = secrets.token_bytes(32).hex()
            conn.execute(
                "INSERT INTO sessions (token, next_index, session_key, created_at) VALUES (?, ?, ?, ?)",
                (token, 0, session_key, int(time.time()))
            )
            conn.commit()
            insert_session_meta(token, "Anonymous")
            return token, 0, session_key
        finally:
            conn.close()


def advance_session(token):
    with DB_LOCK:
        conn = db_connect()
        try:
            conn.execute("UPDATE sessions SET next_index = next_index + 1 WHERE token = ?", (token,))
            conn.commit()
        finally:
            conn.close()


def fetch_question_by_index(index):
    with DB_LOCK:
        conn = db_connect()
        try:
            row = conn.execute(
                "SELECT * FROM questions ORDER BY id ASC LIMIT 1 OFFSET ?",
                (index,)
            ).fetchone()
            return row
        finally:
            conn.close()


def fetch_question_by_id(question_id):
    with DB_LOCK:
        conn = db_connect()
        try:
            return conn.execute("SELECT * FROM questions WHERE id = ?", (question_id,)).fetchone()
        finally:
            conn.close()


def record_answer(token, question_id, answer_index, time_ms, head_compliance):
    with DB_LOCK:
        conn = db_connect()
        try:
            row = conn.execute("SELECT correct_index FROM questions WHERE id = ?", (question_id,)).fetchone()
            correct = 1 if row and int(row["correct_index"]) == int(answer_index) else 0
            conn.execute(
                """
                INSERT INTO session_answers (token, question_id, answer_index, correct, time_ms, head_compliance, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    token,
                    question_id,
                    int(answer_index),
                    correct,
                    int(time_ms),
                    float(head_compliance),
                    int(time.time())
                )
            )
            conn.commit()
        finally:
            conn.close()


def record_event(token, event_type, detail=None):
    with DB_LOCK:
        conn = db_connect()
        try:
            conn.execute(
                "INSERT INTO session_events (token, event_type, detail, created_at) VALUES (?, ?, ?, ?)",
                (token, event_type, detail, int(time.time()))
            )
            conn.commit()
        finally:
            conn.close()


def list_sessions():
    with DB_LOCK:
        conn = db_connect()
        try:
            sessions = conn.execute(
                "SELECT token, name, started_at, completed_at FROM session_meta ORDER BY started_at DESC"
            ).fetchall()
            return sessions
        finally:
            conn.close()


def list_session_answers(token):
    with DB_LOCK:
        conn = db_connect()
        try:
            return conn.execute(
                "SELECT * FROM session_answers WHERE token = ? ORDER BY id ASC",
                (token,)
            ).fetchall()
        finally:
            conn.close()


def list_session_events(token):
    with DB_LOCK:
        conn = db_connect()
        try:
            return conn.execute(
                "SELECT * FROM session_events WHERE token = ? ORDER BY id ASC",
                (token,)
            ).fetchall()
        finally:
            conn.close()


def get_session_review(token):
    with DB_LOCK:
        conn = db_connect()
        try:
            row = conn.execute("SELECT status FROM session_reviews WHERE token = ?", (token,)).fetchone()
            return row["status"] if row else None
        finally:
            conn.close()


def set_session_review(token, status):
    with DB_LOCK:
        conn = db_connect()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO session_reviews (token, status, updated_at) VALUES (?, ?, ?)",
                (token, status, int(time.time()))
            )
            conn.commit()
        finally:
            conn.close()


def list_questions():
    with DB_LOCK:
        conn = db_connect()
        try:
            return conn.execute("SELECT * FROM questions ORDER BY id DESC").fetchall()
        finally:
            conn.close()


def complete_session(token):
    with DB_LOCK:
        conn = db_connect()
        try:
            conn.execute(
                "UPDATE session_meta SET completed_at = ? WHERE token = ?",
                (int(time.time()), token)
            )
            conn.commit()
        finally:
            conn.close()


def call_llm_decoys(question_text, options, correct_index):
    prompt = (
        "Generate two decoy variants of the following multiple-choice question. "
        "Each decoy must be similar in domain, difficulty, and length, but contain a subtle error. "
        "Return JSON only, with keys: decoy_left and decoy_right. Each decoy has keys: question, options (array of 4 strings). "
        "Do not include explanations.\n\n"
        f"Question: {question_text}\n"
        f"Options: {options}\n"
        f"Correct index: {correct_index}\n"
    )

    body = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": "You output strict JSON with no extra text."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.5
    }

    req = Request(
        LLM_API_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {LLM_API_KEY}",
            "Content-Type": "application/json"
        },
        method="POST"
    )

    with urlopen(req, timeout=30) as res:
        raw = res.read().decode("utf-8")
        data = json.loads(raw)
        content = data["choices"][0]["message"]["content"].strip()
        return json.loads(content)


def fallback_decoys(question_text, options):
    decoy_left = {
        "question": question_text.replace("%", " percent"),
        "options": options[::-1]
    }
    decoy_right = {
        "question": question_text.replace("average", "median"),
        "options": options[1:] + options[:1]
    }
    return {"decoy_left": decoy_left, "decoy_right": decoy_right}


def generate_decoys(question_text, options, correct_index):
    if not LLM_API_KEY:
        return fallback_decoys(question_text, options)
    try:
        return call_llm_decoys(question_text, options, correct_index)
    except Exception:
        return fallback_decoys(question_text, options)


def seed_if_needed():
    if fetch_question_count() > 0:
        return
    for item in SEED_QUESTIONS:
        decoys = generate_decoys(item["question"], item["options"], item["correct"])
        payload = dict(item)
        payload["decoy_left"] = decoys["decoy_left"]
        payload["decoy_right"] = decoys["decoy_right"]
        insert_question(payload)


def send_cors(handler):
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")


def send_security_headers(handler):
    handler.send_header("X-Frame-Options", "DENY")
    handler.send_header("X-Content-Type-Options", "nosniff")
    handler.send_header(
        "Content-Security-Policy",
        "default-src 'self'; script-src 'self' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; media-src 'self' blob:; connect-src 'self' http://127.0.0.1:8080;"
    )


def send_text(handler, status, body, content_type="text/html; charset=utf-8"):
    data = body.encode("utf-8")
    handler.send_response(status)
    send_cors(handler)
    send_security_headers(handler)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def serve_file(handler, rel_path, content_type="text/html; charset=utf-8"):
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    full_path = os.path.join(base_dir, rel_path)
    if not os.path.isfile(full_path):
        json_response(handler, 404, {"error": "not_found"})
        return
    with open(full_path, "r", encoding="utf-8") as file:
        send_text(handler, 200, file.read(), content_type)


def json_response(handler, status, payload):
    data = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    send_cors(handler)
    send_security_headers(handler)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def encrypt_payload(session_key_hex, payload_obj):
    key = bytes.fromhex(session_key_hex)
    nonce = secrets.token_bytes(12)
    plaintext = json.dumps(payload_obj).encode("utf-8")
    out = bytearray(len(plaintext))
    counter = 0
    offset = 0
    while offset < len(plaintext):
        counter_bytes = counter.to_bytes(4, "big")
        block = hmac.new(key, nonce + counter_bytes, hashlib.sha256).digest()
        for i in range(min(32, len(plaintext) - offset)):
            out[offset + i] = plaintext[offset + i] ^ block[i]
        offset += 32
        counter += 1
    tag = hmac.new(key, nonce + bytes(out), hashlib.sha256).digest()
    return {
        "nonce": base64.b64encode(nonce).decode("utf-8"),
        "ciphertext": base64.b64encode(bytes(out)).decode("utf-8"),
        "tag": base64.b64encode(tag).decode("utf-8")
    }


def check_rate_limit(ip):
    now = time.time()
    window = RATE_LIMIT.get(ip, [])
    window = [t for t in window if now - t < RATE_LIMIT_WINDOW]
    if len(window) >= RATE_LIMIT_MAX:
        RATE_LIMIT[ip] = window
        return False
    window.append(now)
    RATE_LIMIT[ip] = window
    return True


def parse_json(handler):
    length = int(handler.headers.get("Content-Length", "0") or "0")
    body = handler.rfile.read(length) if length else b"{}"
    try:
        return json.loads(body.decode("utf-8"))
    except json.JSONDecodeError:
        return {}


def get_bearer_token(handler):
    auth = handler.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth.split(" ", 1)[1].strip()
    return ""


def require_admin(handler):
    token = get_bearer_token(handler)
    if not token or not verify_admin_token(token):
        json_response(handler, 401, {"error": "unauthorized"})
        return False
    return True


class Handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(204)
        send_cors(self)
        send_security_headers(self)
        self.end_headers()

    def do_POST(self):
        if self.path == "/api/session/start":
            payload = parse_json(self)
            name = (payload.get("name") or "").strip() or "Candidate"
            token = create_session(name)
            json_response(self, 200, {"sessionToken": token})
            return

        if self.path == "/api/session/next":
            payload = parse_json(self)
            token = payload.get("sessionToken", "")
            token, index = get_or_create_session(token)
            total = fetch_question_count()
            if total == 0:
                json_response(self, 500, {"error": "no_questions"})
                return
            row = fetch_question_by_index(index % total)
            advance_session(token)
            swap = random.choice([True, False])
            left_text = row["decoy_right_text"] if swap else row["decoy_left_text"]
            right_text = row["decoy_left_text"] if swap else row["decoy_right_text"]
            left_opts = row["decoy_right_options_json"] if swap else row["decoy_left_options_json"]
            right_opts = row["decoy_left_options_json"] if swap else row["decoy_right_options_json"]
            time_limit = int(get_setting("time_limit", "20"))
            response = {
                "sessionToken": token,
                "questionId": row["id"],
                "question": row["question_text"],
                "options": json.loads(row["options_json"]),
                "decoyLeft": {
                    "question": left_text,
                    "options": json.loads(left_opts)
                },
                "decoyRight": {
                    "question": right_text,
                    "options": json.loads(right_opts)
                },
                "timeLimit": time_limit
            }
            json_response(self, 200, response)
            return

        if self.path == "/api/session/answer":
            payload = parse_json(self)
            token = payload.get("sessionToken", "")
            question_id = payload.get("questionId")
            answer_index = payload.get("answerIndex", -1)
            time_ms = payload.get("timeMs", 0)
            head_compliance = payload.get("headCompliance", 0)
            if not token or question_id is None:
                json_response(self, 400, {"error": "invalid_payload"})
                return
            record_answer(token, question_id, answer_index, time_ms, head_compliance)
            json_response(self, 200, {"status": "ok"})
            return

        if self.path == "/api/session/event":
            payload = parse_json(self)
            token = payload.get("sessionToken", "")
            event_type = payload.get("type", "")
            detail = payload.get("detail")
            if token and event_type:
                record_event(token, event_type, detail)
            json_response(self, 200, {"status": "ok"})
            return

        if self.path == "/api/session/complete":
            payload = parse_json(self)
            token = payload.get("sessionToken", "")
            if token:
                complete_session(token)
            json_response(self, 200, {"status": "ok"})
            return

        if self.path == "/api/admin/login":
            payload = parse_json(self)
            username = (payload.get("username") or "").strip()
            password = payload.get("password") or ""
            if not username or not password:
                json_response(self, 400, {"error": "invalid_payload"})
                return
            with DB_LOCK:
                conn = db_connect()
                try:
                    row = conn.execute("SELECT password_hash, salt FROM admin_users WHERE username = ?", (username,)).fetchone()
                    if not row:
                        json_response(self, 401, {"error": "invalid_credentials"})
                        return
                    check_hash, _ = hash_password(password, row["salt"])
                    if not hmac.compare_digest(check_hash, row["password_hash"]):
                        json_response(self, 401, {"error": "invalid_credentials"})
                        return
                finally:
                    conn.close()
            token = issue_admin_token(username)
            json_response(self, 200, {"token": token})
            return

        if self.path == "/api/admin/settings":
            if not require_admin(self):
                return
            payload = parse_json(self)
            if "timeLimit" in payload:
                set_setting("time_limit", str(int(payload["timeLimit"])) )
            if "passingThreshold" in payload:
                set_setting("passing_threshold", str(float(payload["passingThreshold"])) )
            if "autoFlagEvents" in payload:
                set_setting("auto_flag_events", json.dumps(list(payload["autoFlagEvents"])) )
            if "headComplianceThreshold" in payload:
                set_setting("head_compliance_threshold", str(float(payload["headComplianceThreshold"])) )
            json_response(self, 200, {"status": "ok"})
            return

        if self.path == "/api/admin/question":
            if not require_admin(self):
                return
            payload = parse_json(self)
            try:
                question_text = payload["question"]
                options = payload["options"]
                correct_index = int(payload["correctIndex"])
                subject = payload.get("subject", "general")
                difficulty = payload.get("difficulty", "medium")
            except Exception:
                json_response(self, 400, {"error": "invalid_payload"})
                return
            decoys = generate_decoys(question_text, options, correct_index)
            insert_question({
                "subject": subject,
                "difficulty": difficulty,
                "question": question_text,
                "options": options,
                "correct": correct_index,
                "decoy_left": decoys["decoy_left"],
                "decoy_right": decoys["decoy_right"]
            })
            json_response(self, 200, {"status": "ok"})
            return

        if self.path == "/api/admin/password":
            if not require_admin(self):
                return
            payload = parse_json(self)
            current = payload.get("currentPassword") or ""
            new_pw = payload.get("newPassword") or ""
            if not current or not new_pw:
                json_response(self, 400, {"error": "invalid_payload"})
                return
            with DB_LOCK:
                conn = db_connect()
                try:
                    row = conn.execute("SELECT password_hash, salt FROM admin_users WHERE username = ?", (ADMIN_USER,)).fetchone()
                    if not row:
                        json_response(self, 401, {"error": "invalid_credentials"})
                        return
                    check_hash, _ = hash_password(current, row["salt"])
                    if not hmac.compare_digest(check_hash, row["password_hash"]):
                        json_response(self, 401, {"error": "invalid_credentials"})
                        return
                    new_hash, new_salt = hash_password(new_pw)
                    conn.execute(
                        "UPDATE admin_users SET password_hash = ?, salt = ? WHERE username = ?",
                        (new_hash, new_salt, ADMIN_USER)
                    )
                    conn.commit()
                finally:
                    conn.close()
            json_response(self, 200, {"status": "ok"})
            return

        if self.path == "/api/admin/session/review":
            if not require_admin(self):
                return
            payload = parse_json(self)
            token = payload.get("token", "")
            status = payload.get("status", "")
            if token and status in ("cleared", "escalated"):
                set_session_review(token, status)
                json_response(self, 200, {"status": "ok"})
                return
            json_response(self, 400, {"error": "invalid_payload"})
            return

        json_response(self, 404, {"error": "not_found"})

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            serve_file(self, "index.html")
            return
        if self.path == "/admin" or self.path == "/admin.html":
            serve_file(self, "admin.html")
            return
        if self.path == "/health":
            json_response(self, 200, {"status": "ok"})
            return
        if self.path == "/api/admin/settings":
            if not require_admin(self):
                return
            response = {
                "timeLimit": int(get_setting("time_limit", "20")),
                "passingThreshold": float(get_setting("passing_threshold", "0.7")),
                "autoFlagEvents": json.loads(get_setting("auto_flag_events", "[]")),
                "headComplianceThreshold": float(get_setting("head_compliance_threshold", "0.6"))
            }
            json_response(self, 200, response)
            return
        if self.path == "/api/admin/sessions":
            if not require_admin(self):
                return
            auto_flag = set(json.loads(get_setting("auto_flag_events", "[]")))
            compliance_threshold = float(get_setting("head_compliance_threshold", "0.6"))
            response = []
            for row in list_sessions():
                token = row["token"]
                answers = list_session_answers(token)
                events = list_session_events(token)
                correct = sum(1 for a in answers if a["correct"] == 1)
                total = len(answers)
                score = (correct / total) if total else 0
                avg_compliance = (sum(a["head_compliance"] for a in answers) / total) if total else 1
                flagged = any(e["event_type"] in auto_flag for e in events) or avg_compliance < compliance_threshold
                review = get_session_review(token)
                if row["completed_at"] is None:
                    status = "In progress"
                elif review == "cleared":
                    status = "Cleared"
                elif review == "escalated":
                    status = "Escalated"
                else:
                    status = "Flagged" if flagged else "Clean"
                duration = (row["completed_at"] or int(time.time())) - row["started_at"]
                response.append({
                    "token": token,
                    "name": row["name"],
                    "startedAt": row["started_at"],
                    "completedAt": row["completed_at"],
                    "durationSec": duration,
                    "score": score,
                    "status": status,
                    "review": review
                })
            json_response(self, 200, response)
            return
        if self.path.startswith("/api/admin/session/"):
            if not require_admin(self):
                return
            token = self.path.split("/api/admin/session/", 1)[1]
            answers = list_session_answers(token)
            events = list_session_events(token)
            review = get_session_review(token)
            response_answers = []
            for ans in answers:
                q = fetch_question_by_id(ans["question_id"])
                response_answers.append({
                    "questionId": ans["question_id"],
                    "question": q["question_text"] if q else "",
                    "options": json.loads(q["options_json"]) if q else [],
                    "answerIndex": ans["answer_index"],
                    "correctIndex": q["correct_index"] if q else -1,
                    "correct": ans["correct"],
                    "timeMs": ans["time_ms"],
                    "headCompliance": ans["head_compliance"],
                    "createdAt": ans["created_at"]
                })
            response_events = [
                {
                    "type": e["event_type"],
                    "detail": e["detail"],
                    "createdAt": e["created_at"]
                } for e in events
            ]
            json_response(self, 200, {"answers": response_answers, "events": response_events, "review": review})
            return
        if self.path == "/api/admin/questions":
            if not require_admin(self):
                return
            rows = list_questions()
            response = []
            for row in rows:
                response.append({
                    "id": row["id"],
                    "subject": row["subject"],
                    "difficulty": row["difficulty"],
                    "question": row["question_text"],
                    "options": json.loads(row["options_json"]),
                    "correctIndex": row["correct_index"],
                    "decoyLeft": {
                        "question": row["decoy_left_text"],
                        "options": json.loads(row["decoy_left_options_json"])
                    },
                    "decoyRight": {
                        "question": row["decoy_right_text"],
                        "options": json.loads(row["decoy_right_options_json"])
                    }
                })
            json_response(self, 200, response)
            return
        json_response(self, 404, {"error": "not_found"})

    def log_message(self, format, *args):
        return


def main():
    init_db()
    seed_if_needed()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"server_running http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
