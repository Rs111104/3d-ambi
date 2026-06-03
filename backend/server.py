import json
import os
import random
import sqlite3
import socket
import threading
import time
import uuid
    def do_GET(self):
        try:
            parsed = urlparse(self.path)
            path = parsed.path
            if path == "/" or path == "/index.html":
                serve_file(self, "index.html")
                return
            if path == "/test":
                serve_file(self, "index.html")
                return
            if path == "/admin" or path == "/admin.html":
                serve_file(self, "admin.html")
                return
            if path == "/styles.css":
                serve_file(self, "styles.css", "text/css; charset=utf-8")
                return
            if path == "/health":
                try:
                    questions = fetch_question_count()
                    db_status = "connected"
                except Exception:
                    questions = 0
                    db_status = "error"
                json_response(self, 200, {"status": "ok", "db": db_status, "questions": questions})
                return
            if path == "/api/local-access":
                ip = get_local_ip()
                json_response(self, 200, {"ip": ip, "url": f"http://{ip}:{PORT}/test"})
                return
            if path == "/api/admin/settings":
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
            if path == "/api/admin/sessions":
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
                    integrity = compute_integrity(answers, events)
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
                        "integrityScore": integrity,
                        "status": status,
                        "review": review
                    })
                json_response(self, 200, response)
                return
            if path.startswith("/api/admin/session/"):
                if not require_admin(self):
                    return
                token = path.split("/api/admin/session/", 1)[1]
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
                json_response(self, 200, {
                    "answers": response_answers,
                    "events": response_events,
                    "review": review,
                    "notes": [
                        {"note": n["note"], "createdAt": n["created_at"]} for n in list_session_notes(token)
                    ],
                    "integrityScore": compute_integrity(answers, events)
                })
                return
            if path == "/api/admin/live-sessions":
                if not require_admin(self):
                    return
                response = []
                for row in list_sessions():
                    if row["completed_at"] is not None:
                        continue
                    answers = list_session_answers(row["token"])
                    compliance = (sum(a["head_compliance"] for a in answers) / len(answers)) if answers else 1
                    response.append({
                        "token": row["token"],
                        "name": row["name"],
                        "currentQuestion": len(answers) + 1,
                        "elapsedSec": int(time.time()) - row["started_at"],
                        "headCompliance": compliance
                    })
                json_response(self, 200, response)
                return
            if path == "/api/admin/sessions/live":
                if not require_admin(self):
                    return
                response = []
                for row in list_sessions():
                    if row["completed_at"] is not None:
                        continue
                    answers = list_session_answers(row["token"])
                    compliance = (sum(a["head_compliance"] for a in answers) / len(answers)) if answers else 1
                    response.append({
                        "token": row["token"],
                        "name": row["name"],
                        "currentQuestion": len(answers) + 1,
                        "elapsedSec": int(time.time()) - row["started_at"],
                        "headCompliance": compliance
                    })
                json_response(self, 200, response)
                return
            if path == "/api/admin/questions":
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
                            "options": json.loads(row["decoy_left_options_json"]),
                            "quality": row["decoy_left_quality"]
                        },
                        "decoyRight": {
                            "question": row["decoy_right_text"],
                            "options": json.loads(row["decoy_right_options_json"]),
                            "quality": row["decoy_right_quality"]
                        }
                    })
                json_response(self, 200, response)
                return
            if path == "/api/admin/decoy-audit":
                if not require_admin(self):
                    return
                json_response(self, 200, decoy_audit_rows())
                return
            if path == "/api/admin/test-sets":
                if not require_admin(self):
                    return
                out = []
                for item in list_test_sets():
                    invites = []
                    for invite in item["invites"]:
                        answers = list_session_answers(invite["session_token"]) if invite["session_token"] else []
                        total = len(answers)
                        correct = sum(1 for a in answers if a["correct"] == 1)
                        invites.append({
                            "token": invite["token"],
                            "candidateName": invite["candidate_name"],
                            "status": invite["status"],
                            "score": (correct / total) if total else 0
                        })
                    out.append({
                        "id": item["set"]["id"],
                        "name": item["set"]["name"],
                        "description": item["set"]["description"],
                        "timeLimitOverride": item["set"]["time_limit_override"],
                        "passingThresholdOverride": item["set"]["passing_threshold_override"],
                        "questionIds": [q["question_id"] for q in item["questions"]],
                        "invites": invites
                    })
                json_response(self, 200, out)
                return
            if path == "/api/admin/sessions/export":
                if not require_admin(self):
                    return
                rows = ["candidate name,date,score,integrity score,time taken,flagged events count"]
                flagged_types = {"tab_hidden", "window_blur", "right_click", "devtools_open", "face_lost", "clipboard_attempt", "liveness_fail", "screen_capture_attempt"}
                for row in list_sessions():
                    if row["completed_at"] is None:
                        continue
                    answers = list_session_answers(row["token"])
                    events = list_session_events(row["token"])
                    total = len(answers)
                    correct = sum(1 for a in answers if a["correct"] == 1)
                    score = int(round((correct / total) * 100)) if total else 0
                    integrity = compute_integrity(answers, events)
                    flagged = sum(1 for e in events if e["event_type"] in flagged_types)
                    duration = int(row["completed_at"]) - int(row["started_at"])
                    safe_name = '"' + str(row["name"]).replace('"', '""') + '"'
                    rows.append(
                        f'{safe_name},{time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(row["started_at"]))},{score},{integrity},{duration},{flagged}'
                    )
                send_text(self, 200, "\n".join(rows), "text/csv; charset=utf-8")
                return
            if path.startswith("/api/invite/"):
                token = path.split("/api/invite/", 1)[1]
                invite = fetch_invite(token)
                if not invite:
                    json_response(self, 404, {"error": "not_found"})
                    return
                json_response(self, 200, {
                    "token": invite["token"],
                    "candidateName": invite["candidate_name"],
                    "status": invite["status"],
                    "setId": invite["set_id"]
                })
                return
            if path == "/api/session/status":
                token = parsed.query.split("token=", 1)[1] if "token=" in parsed.query else ""
                if not token:
                    bad_request(self, "missing_token")
                    return
                meta = None
                with DB_LOCK:
                    conn = db_connect()
                    try:
                        meta = conn.execute("SELECT started_at, completed_at FROM session_meta WHERE token = ?", (token,)).fetchone()
                    finally:
                        conn.close()
                if not meta:
                    json_response(self, 404, {"error": "session_not_found"})
                    return
                json_response(self, 200, {"status": "complete" if meta["completed_at"] else "in_progress", "expired": False})
                return
            if path == "/api/session/result":
                token = parsed.query.split("token=", 1)[1] if "token=" in parsed.query else ""
                if not token:
                    bad_request(self, "missing_token")
                    return
                answers = list_session_answers(token)
                meta = None
                with DB_LOCK:
                    conn = db_connect()
                    try:
                        meta = conn.execute("SELECT started_at, completed_at FROM session_meta WHERE token = ?", (token,)).fetchone()
                    finally:
                        conn.close()
                total = len(answers)
                correct = sum(1 for a in answers if a["correct"] == 1)
                passing = float(get_setting("passing_threshold", "0.7"))
                score = (correct / total) if total else 0
                time_taken_ms = int(((meta["completed_at"] or int(time.time())) - meta["started_at"]) * 1000) if meta else 0
                json_response(self, 200, {
                    "score": correct,
                    "total": total,
                    "passed": score >= passing,
                    "timeTakenMs": time_taken_ms,
                    "passingThreshold": passing
                })
                return
            json_response(self, 404, {"error": "not_found"})
            return
        except Exception:
            import traceback
            traceback.print_exc()
            try:
                json_response(self, 500, {"error": "internal_server_error"})
            except Exception:
                pass
            return
                "ALTER TABLE sessions ADD COLUMN issued_at_ms INTEGER",
                "ALTER TABLE sessions ADD COLUMN answer_received INTEGER NOT NULL DEFAULT 1",
                "ALTER TABLE sessions ADD COLUMN question_order_json TEXT",
                "ALTER TABLE sessions ADD COLUMN invite_token TEXT"
            ]:
                try:
                    conn.execute(stmt)
                except sqlite3.OperationalError:
                    pass
            try:
                conn.execute("ALTER TABLE session_answers ADD COLUMN server_received_at INTEGER")
            except sqlite3.OperationalError:
                pass
            for stmt in [
                "ALTER TABLE test_sets ADD COLUMN description TEXT NOT NULL DEFAULT ''",
                "ALTER TABLE test_sets ADD COLUMN time_limit_override INTEGER",
                "ALTER TABLE test_sets ADD COLUMN passing_threshold_override REAL"
            ]:
                try:
                    conn.execute(stmt)
                except sqlite3.OperationalError:
                    pass
            conn.commit()
        finally:
            conn.close()
    ensure_admin_user()
    ensure_default_settings()
    ensure_question_tags()
    validate_decoys_on_startup()


def ensure_question_tags():
    mapping = {
        "logic": "logical_reasoning",
        "numerical": "numerical_aptitude",
        "verbal": "verbal_reasoning",
        "general": "logical_reasoning"
    }
    with DB_LOCK:
        conn = db_connect()
        try:
            for old, new in mapping.items():
                conn.execute("UPDATE questions SET subject = ? WHERE subject = ?", (new, old))
            conn.commit()
        finally:
            conn.close()


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
                    decoy_left_text, decoy_left_options_json, decoy_left_quality,
                    decoy_right_text, decoy_right_options_json, decoy_right_quality, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["subject"],
                    payload["difficulty"],
                    payload["question"],
                    json.dumps(payload["options"]),
                    payload["correct"],
                    payload["decoy_left"]["question"],
                    json.dumps(payload["decoy_left"]["options"]),
                    int(payload.get("decoy_left_quality", 8)),
                    payload["decoy_right"]["question"],
                    json.dumps(payload["decoy_right"]["options"]),
                    int(payload.get("decoy_right_quality", 8)),
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


def derive_session_key(token, nonce_hex=None):
    ikm = token.encode("utf-8")
    salt = b"3d-ambi-v1"
    prk = hmac.new(salt, ikm, hashlib.sha256).digest()
    okm = hmac.new(prk, b"session-key\x01", hashlib.sha256).digest()
    return okm.hex()


def create_question_order(set_id=None):
    with DB_LOCK:
        conn = db_connect()
        try:
            if set_id:
                rows = conn.execute(
                    """
                    SELECT q.id FROM questions q
                    JOIN test_set_questions tsq ON tsq.question_id = q.id
                    WHERE tsq.set_id = ?
                    ORDER BY tsq.position ASC
                    """,
                    (set_id,)
                ).fetchall()
            else:
                rows = conn.execute("SELECT id FROM questions ORDER BY id ASC").fetchall()
            ids = [int(row["id"]) for row in rows]
            random.shuffle(ids)
            return ids
        finally:
            conn.close()


def create_session(name, set_id=None, invite_token=None):
    token = str(uuid.uuid4())
    session_nonce = secrets.token_bytes(16).hex()
    session_key = derive_session_key(token)
    question_order = create_question_order(set_id)
    with DB_LOCK:
        conn = db_connect()
        try:
            conn.execute(
                """
                INSERT INTO sessions (
                    token, next_index, session_key, session_nonce, question_order_json, invite_token, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (token, 0, session_key, session_nonce, json.dumps(question_order), invite_token, int(time.time()))
            )
            if invite_token:
                conn.execute(
                    "UPDATE candidate_invites SET status = ?, session_token = ?, used_at = ? WHERE token = ?",
                    ("in_progress", token, int(time.time()), invite_token)
                )
            conn.commit()
        finally:
            conn.close()
    insert_session_meta(token, name)
    return token


def get_or_create_session(token):
    with DB_LOCK:
        conn = db_connect()
        try:
            if token:
                row = conn.execute(
                    """
                    SELECT token, next_index, session_key, questions_served, delivered_index, delivered_question_id,
                           issued_at_ms, answer_received, question_order_json
                    FROM sessions WHERE token = ?
                    """,
                    (token,)
                ).fetchone()
                if row:
                    return row
            token = str(uuid.uuid4())
            session_nonce = secrets.token_bytes(16).hex()
            session_key = derive_session_key(token)
            question_order = create_question_order()
            conn.execute(
                "INSERT INTO sessions (token, next_index, session_key, session_nonce, question_order_json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (token, 0, session_key, session_nonce, json.dumps(question_order), int(time.time()))
            )
            conn.commit()
            insert_session_meta(token, "Anonymous")
            return conn.execute(
                """
                SELECT token, next_index, session_key, questions_served, delivered_index, delivered_question_id,
                       issued_at_ms, answer_received, question_order_json
                FROM sessions WHERE token = ?
                """,
                (token,)
            ).fetchone()
        finally:
            conn.close()


def mark_question_issued(token, index, question_id):
    with DB_LOCK:
        conn = db_connect()
        try:
            conn.execute(
                """
                UPDATE sessions
                SET next_index = next_index + 1,
                    questions_served = questions_served + 1,
                    delivered_index = ?,
                    delivered_question_id = ?,
                    issued_at_ms = ?,
                    answer_received = 0
                WHERE token = ?
                """,
                (index, question_id, int(time.time() * 1000), token)
            )
            conn.execute(
                "INSERT INTO question_log (token, question_id, question_index, served_at) VALUES (?, ?, ?, ?)",
                (token, question_id, index, time.time())
            )
            conn.commit()
        finally:
            conn.close()


def mark_answer_received(token):
    with DB_LOCK:
        conn = db_connect()
        try:
            conn.execute("UPDATE sessions SET answer_received = 1 WHERE token = ?", (token,))
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


def fetch_question_for_session(session_row):
    order = []
    if session_row["question_order_json"]:
        try:
            order = json.loads(session_row["question_order_json"])
        except json.JSONDecodeError:
            order = []
    if order:
        question_id = order[int(session_row["next_index"]) % len(order)]
        return fetch_question_by_id(question_id)
    total = fetch_question_count()
    if total == 0:
        return None
    return fetch_question_by_index(int(session_row["next_index"]) % total)


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
            session_row = conn.execute(
                "SELECT issued_at_ms FROM sessions WHERE token = ?",
                (token,)
            ).fetchone()
            if not session_row or not session_row["issued_at_ms"]:
                return False, "question_not_served"
            log_row = conn.execute(
                "SELECT served_at FROM question_log WHERE token = ? AND question_id = ? ORDER BY id DESC LIMIT 1",
                (token, question_id)
            ).fetchone()
            if not log_row:
                return False, "question_out_of_sequence"
            served_at = float(log_row["served_at"])
            elapsed_sec = time.time() - served_at
            time_limit_sec = int(get_setting("time_limit", "20"))
            server_time_ms = max(0, int(elapsed_sec * 1000))
            if elapsed_sec < 1.5:
                conn.execute("INSERT INTO session_events (token, event_type, detail, created_at) VALUES (?, ?, ?, ?)", (token, "too_fast", None, int(time.time())))
                conn.commit()
                return False, "too_fast"
            if elapsed_sec > time_limit_sec + 60:
                conn.execute("INSERT INTO session_events (token, event_type, detail, created_at) VALUES (?, ?, ?, ?)", (token, "too_slow", None, int(time.time())))
                conn.commit()
                return False, "too_slow"
            row = conn.execute("SELECT correct_index FROM questions WHERE id = ?", (question_id,)).fetchone()
            correct = 1 if row and int(row["correct_index"]) == int(answer_index) else 0
            if abs(server_time_ms - int(time_ms)) > 3000:
                conn.execute(
                    "INSERT INTO session_events (token, event_type, detail, created_at) VALUES (?, ?, ?, ?)",
                    (
                        token,
                        "timing_mismatch",
                        json.dumps({"clientMs": int(time_ms), "serverMs": server_time_ms}),
                        int(time.time())
                    )
                )
            conn.execute(
                """
                INSERT INTO session_answers (
                    token, question_id, answer_index, correct, time_ms, head_compliance, server_received_at, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    token,
                    question_id,
                    int(answer_index),
                    correct,
                    server_time_ms,
                    float(head_compliance),
                    int(time.time()),
                    int(time.time())
                )
            )
            conn.execute("UPDATE sessions SET answer_received = 1 WHERE token = ?", (token,))
            conn.commit()
            return True, "ok"
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
    integrity = compute_integrity(list_session_answers(token), list_session_events(token))
    with DB_LOCK:
        conn = db_connect()
        try:
            conn.execute(
                "UPDATE session_meta SET completed_at = ? WHERE token = ?",
                (int(time.time()), token)
            )
            conn.execute(
                "UPDATE sessions SET integrity_score = ? WHERE token = ?",
                (integrity, token)
            )
            conn.execute(
                "UPDATE candidate_invites SET status = ?, completed_at = ? WHERE session_token = ?",
                ("completed", int(time.time()), token)
            )
            conn.commit()
        finally:
            conn.close()


def list_session_notes(token):
    with DB_LOCK:
        conn = db_connect()
        try:
            return conn.execute("SELECT * FROM session_notes WHERE token = ? ORDER BY created_at DESC", (token,)).fetchall()
        finally:
            conn.close()


def add_session_note(token, note):
    with DB_LOCK:
        conn = db_connect()
        try:
            conn.execute(
                "INSERT INTO session_notes (token, note, created_at) VALUES (?, ?, ?)",
                (token, note, int(time.time()))
            )
            conn.commit()
        finally:
            conn.close()


def session_score(token):
    answers = list_session_answers(token)
    total = len(answers)
    correct = sum(1 for a in answers if a["correct"] == 1)
    return (correct / total) if total else 0


def compute_integrity(answers, events):
    flagged_types = {"tab_hidden", "window_blur", "devtools_open", "clipboard_attempt", "liveness_fail", "face_lost", "screen_capture_attempt", "right_click"}
    score = 100
    score -= 15 * len({e["event_type"] for e in events if e["event_type"] in flagged_types})
    threshold = float(get_setting("head_compliance_threshold", "0.6"))
    score -= 10 * sum(1 for a in answers if float(a["head_compliance"]) < threshold)
    suspicious_timing = any(
        e["event_type"] in ("timing_mismatch", "too_fast", "too_slow", "answer_too_fast", "answer_stale") for e in events
    ) or any(int(a["time_ms"]) < 2000 for a in answers)
    if suspicious_timing:
        score -= 20
    return max(0, min(100, int(score)))


def list_test_sets():
    with DB_LOCK:
        conn = db_connect()
        try:
            sets = conn.execute("SELECT * FROM test_sets ORDER BY created_at DESC").fetchall()
            out = []
            for item in sets:
                questions = conn.execute(
                    "SELECT question_id FROM test_set_questions WHERE set_id = ? ORDER BY position ASC",
                    (item["id"],)
                ).fetchall()
                invites = conn.execute(
                    "SELECT * FROM candidate_invites WHERE set_id = ? ORDER BY created_at DESC",
                    (item["id"],)
                ).fetchall()
                out.append({"set": item, "questions": questions, "invites": invites})
            return out
        finally:
            conn.close()


def create_test_set(name, description, question_ids, time_limit_override=None, passing_threshold_override=None):
    set_id = secrets.token_urlsafe(8)
    with DB_LOCK:
        conn = db_connect()
        try:
            conn.execute(
                """
                INSERT INTO test_sets (
                    id, name, description, time_limit_override, passing_threshold_override, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (set_id, name, description, time_limit_override, passing_threshold_override, int(time.time()))
            )
            for pos, question_id in enumerate(question_ids):
                conn.execute(
                    "INSERT INTO test_set_questions (set_id, question_id, position) VALUES (?, ?, ?)",
                    (set_id, int(question_id), pos)
                )
            conn.commit()
            return set_id
        finally:
            conn.close()


def create_invite(set_id, candidate_name):
    token = secrets.token_urlsafe(18)
    with DB_LOCK:
        conn = db_connect()
        try:
            conn.execute(
                "INSERT INTO candidate_invites (token, set_id, candidate_name, status, created_at) VALUES (?, ?, ?, ?, ?)",
                (token, set_id, candidate_name, "unused", int(time.time()))
            )
            conn.commit()
            return token
        finally:
            conn.close()


def fetch_invite(token):
    with DB_LOCK:
        conn = db_connect()
        try:
            return conn.execute("SELECT * FROM candidate_invites WHERE token = ?", (token,)).fetchone()
        finally:
            conn.close()


def get_session_time_limit(token):
    with DB_LOCK:
        conn = db_connect()
        try:
            row = conn.execute(
                """
                SELECT ts.time_limit_override
                FROM sessions s
                JOIN candidate_invites ci ON ci.token = s.invite_token
                JOIN test_sets ts ON ts.id = ci.set_id
                WHERE s.token = ?
                """,
                (token,)
            ).fetchone()
            if row and row["time_limit_override"]:
                return int(row["time_limit_override"])
        finally:
            conn.close()
    return int(get_setting("time_limit", "20"))


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


def score_decoy_quality(decoy_text):
    if not LLM_API_KEY:
        return 8
    prompt = (
        "On a scale of 1-10, how convincing is this as a real exam question to someone who has not seen the original? "
        f"Question: {decoy_text}. Return only the number."
    )
    body = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": "Return only a number from 1 to 10."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0
    }
    try:
        req = Request(
            LLM_API_URL,
            data=json.dumps(body).encode("utf-8"),
            headers={"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"},
            method="POST"
        )
        with urlopen(req, timeout=20) as res:
            data = json.loads(res.read().decode("utf-8"))
            raw = data["choices"][0]["message"]["content"].strip()
            return max(1, min(10, int(float(raw))))
    except Exception:
        return 8


def generate_decoys(question_text, options, correct_index):
    if not LLM_API_KEY:
        return fallback_decoys(question_text, options)
    try:
        return call_llm_decoys(question_text, options, correct_index)
    except Exception:
        return fallback_decoys(question_text, options)


def regenerate_question_decoys(question_id):
    with DB_LOCK:
        conn = db_connect()
        try:
            row = conn.execute("SELECT * FROM questions WHERE id = ?", (question_id,)).fetchone()
            if not row:
                return False
            options = json.loads(row["options_json"])
            decoys = generate_decoys(row["question_text"], options, row["correct_index"])
            left_quality = score_decoy_quality(decoys["decoy_left"]["question"])
            right_quality = score_decoy_quality(decoys["decoy_right"]["question"])
            conn.execute(
                """
                UPDATE questions
                SET decoy_left_text = ?, decoy_left_options_json = ?, decoy_left_quality = ?,
                    decoy_right_text = ?, decoy_right_options_json = ?, decoy_right_quality = ?
                WHERE id = ?
                """,
                (
                    decoys["decoy_left"]["question"],
                    json.dumps(decoys["decoy_left"]["options"]),
                    left_quality,
                    decoys["decoy_right"]["question"],
                    json.dumps(decoys["decoy_right"]["options"]),
                    right_quality,
                    question_id
                )
            )
            conn.commit()
            return True
        finally:
            conn.close()


def validate_decoys_on_startup():
    missing = []
    with DB_LOCK:
        conn = db_connect()
        try:
            rows = conn.execute("SELECT * FROM questions ORDER BY id ASC").fetchall()
            for row in rows:
                left_missing = not row["decoy_left_text"] or len(row["decoy_left_text"].strip()) < 20
                right_missing = not row["decoy_right_text"] or len(row["decoy_right_text"].strip()) < 20
                if left_missing or right_missing:
                    missing.append(row["id"])
        finally:
            conn.close()
    if not missing:
        return
    if not LLM_API_KEY:
        print(f"WARNING: {len(missing)} questions are missing decoys. Set LLM_API_KEY to auto-generate them.")
        return
    for question_id in missing:
        regenerate_question_decoys(question_id)


def decoy_audit_rows():
    rows = list_questions()
    out = []
    for row in rows:
        left_ok = bool(row["decoy_left_text"] and len(row["decoy_left_text"].strip()) >= 20)
        right_ok = bool(row["decoy_right_text"] and len(row["decoy_right_text"].strip()) >= 20)
        if left_ok and right_ok:
            status = "complete"
        elif left_ok:
            status = "missing_right"
        elif right_ok:
            status = "missing_left"
        else:
            status = "missing_both"
        out.append({
            "id": row["id"],
            "question": row["question_text"],
            "leftOk": left_ok,
            "rightOk": right_ok,
            "status": status
        })
    return out


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
    nonce = getattr(handler, "csp_nonce", "")
    script_src = f"'self' 'nonce-{nonce}' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com" if nonce else "'self' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com"
    handler.send_header("X-Frame-Options", "DENY")
    handler.send_header("X-Content-Type-Options", "nosniff")
    handler.send_header(
        "Content-Security-Policy",
        f"default-src 'self'; script-src {script_src}; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; media-src 'self' blob:; connect-src 'self' http:;"
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
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
    full_path = os.path.join(base_dir, rel_path)
    if not os.path.isfile(full_path):
        json_response(handler, 404, {"error": "not_found"})
        return
    with open(full_path, "r", encoding="utf-8") as file:
        body = file.read()
    if rel_path.endswith(".html"):
        nonce = secrets.token_urlsafe(16)
        handler.csp_nonce = nonce
        body = body.replace("<script ", f"<script nonce=\"{nonce}\" ")
        body = body.replace("<script>", f"<script nonce=\"{nonce}\">")
    send_text(handler, 200, body, content_type)


def json_response(handler, status, payload, extra_headers=None):
    data = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    send_cors(handler)
    send_security_headers(handler)
    for key, value in (extra_headers or {}).items():
        handler.send_header(key, value)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


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


def check_session_rate_limit(token):
    if not token:
        return True
    now = time.time()
    key = f"session:{token}"
    window = RATE_LIMIT.get(key, [])
    window = [t for t in window if now - t < RATE_LIMIT_WINDOW]
    if len(window) >= RATE_LIMIT_MAX:
        RATE_LIMIT[key] = window
        return False
    window.append(now)
    RATE_LIMIT[key] = window
    return True


def rate_limited(handler):
    json_response(handler, 429, {"error": "rate_limited"}, {"Retry-After": "60"})


def bad_request(handler, error):
    json_response(handler, 400, {"error": error, "reason": error})


def require_string(payload, key, allow_empty=False):
    value = payload.get(key)
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value and not allow_empty:
        return None
    return value


def require_number(payload, key, min_value=None, max_value=None):
    value = payload.get(key)
    if not isinstance(value, (int, float)):
        return None
    if min_value is not None and value < min_value:
        return None
    if max_value is not None and value > max_value:
        return None
    return value


def parse_json(handler):
    length = int(handler.headers.get("Content-Length", "0") or "0")
    body = handler.rfile.read(length) if length else b"{}"
    try:
        payload = json.loads(body.decode("utf-8"))
        if isinstance(payload, dict) and isinstance(payload.get("sessionToken"), str):
            handler._token_tail = payload["sessionToken"][-6:]
        return payload
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


def get_local_ip():
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
        sock.close()
        return ip
    except Exception:
        return "127.0.0.1"


class Handler(BaseHTTPRequestHandler):
    def handle_one_request(self):
        self._request_started = time.time()
        super().handle_one_request()

    def send_response(self, code, message=None):
        self._response_status = code
        super().send_response(code, message)

    def finish(self):
        try:
            latency_ms = int((time.time() - getattr(self, "_request_started", time.time())) * 1000)
            print(json.dumps({
                "ts": int(time.time()),
                "method": getattr(self, "command", ""),
                "path": getattr(self, "path", ""),
                "token_tail": getattr(self, "_token_tail", None),
                "status": getattr(self, "_response_status", 0),
                "ms": latency_ms
            }))
        except Exception:
            pass
        super().finish()

    def do_HEAD(self):
        parsed = urlparse(self.path)
        path = parsed.path
        # Static pages: respond with headers only
        if path == "/" or path == "/index.html" or path == "/test":
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
            full_path = os.path.join(base_dir, "index.html")
            if not os.path.isfile(full_path):
                self.send_response(404)
                send_cors(self)
                send_security_headers(self)
                self.end_headers()
                return
            with open(full_path, "rb") as fh:
                body = fh.read()
            self.send_response(200)
            send_cors(self)
            send_security_headers(self)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            return

        # Health endpoint
        if path == "/health":
            try:
                questions = fetch_question_count()
                db_status = "connected"
            except Exception:
                questions = 0
                db_status = "error"
            payload = json.dumps({"status": "ok", "db": db_status, "questions": questions}).encode("utf-8")
            self.send_response(200)
            send_cors(self)
            send_security_headers(self)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            return

    def do_OPTIONS(self):
        self.send_response(204)
        send_cors(self)
        send_security_headers(self)
        self.end_headers()

    def do_POST(self):
        try:
            if self.path.startswith("/api/session/") and self.path == "/api/session/start":
                if not check_rate_limit(self.client_address[0]):
                    rate_limited(self)
                    return

            if self.path == "/api/session/start":
                payload = parse_json(self)
                if not isinstance(payload, dict):
                    bad_request(self, "invalid_json")
                    return
                name = (payload.get("name") or "").strip() or "Candidate"
                if not isinstance(name, str) or len(name) > 120:
                    bad_request(self, "invalid_name")
                    return
                set_id = (payload.get("setId") or "").strip() or None
                invite_token = (payload.get("inviteToken") or "").strip() or None
                if invite_token:
                    invite = fetch_invite(invite_token)
                    if (
                        not invite
                        or invite["status"] != "unused"
                        or int(time.time()) - int(invite["created_at"]) > 72 * 60 * 60
                    ):
                        json_response(self, 409, {"error": "invite_unavailable"})
                        return
                    set_id = invite["set_id"]
                    name = invite["candidate_name"] or name
                token = create_session(name, set_id, invite_token)
                json_response(self, 200, {"sessionToken": token})
                return

            if self.path == "/api/session/next":
                payload = parse_json(self)
                token = require_string(payload, "sessionToken")
                if not token:
                    bad_request(self, "missing_sessionToken")
                    return
                if not check_session_rate_limit(token):
                    rate_limited(self)
                    return
                session_row = get_or_create_session(token)
                if not session_row:
                    json_response(self, 400, {"error": "invalid_session"})
                    return
                token = session_row["token"]
                row = fetch_question_for_session(session_row)
                if not row:
                    json_response(self, 500, {"error": "no_questions"})
                    return
                mark_question_issued(token, int(session_row["next_index"]), row["id"])
                swap = random.choice([True, False])
                left_text = row["decoy_right_text"] if swap else row["decoy_left_text"]
                right_text = row["decoy_left_text"] if swap else row["decoy_right_text"]
                left_opts = row["decoy_right_options_json"] if swap else row["decoy_left_options_json"]
                right_opts = row["decoy_left_options_json"] if swap else row["decoy_right_options_json"]
                time_limit = get_session_time_limit(token)
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
                    "timeLimit": time_limit,
                    "totalQuestions": len(json.loads(session_row["question_order_json"] or "[]")) or fetch_question_count()
                }
                json_response(self, 200, response)
                return

            if self.path == "/api/session/answer":
                payload = parse_json(self)
                token = require_string(payload, "sessionToken")
                question_id = require_number(payload, "questionId", 1)
                answer_index = require_number(payload, "answerIndex", -1, 3)
                time_ms = require_number(payload, "timeMs", 0)
                head_compliance = require_number(payload, "headCompliance", 0, 1)
                if not token or question_id is None or answer_index is None or time_ms is None or head_compliance is None:
                    bad_request(self, "invalid_answer_payload")
                    return
                if not check_session_rate_limit(token):
                    rate_limited(self)
                    return
                ok, reason = record_answer(token, question_id, answer_index, time_ms, head_compliance)
                if not ok:
                    bad_request(self, reason)
                    return
                json_response(self, 200, {"status": "ok"})
                return

            if self.path == "/api/session/event":
                payload = parse_json(self)
                token = require_string(payload, "sessionToken")
                event_type = require_string(payload, "type")
                detail = payload.get("detail")
                if not token or not event_type:
                    bad_request(self, "invalid_event_payload")
                    return
                if not check_session_rate_limit(token):
                    rate_limited(self)
                    return
                if token and event_type:
                    record_event(token, event_type, detail)
                json_response(self, 200, {"status": "ok"})
                return

            if self.path == "/api/session/complete":
                payload = parse_json(self)
                token = require_string(payload, "sessionToken")
                if not token:
                    bad_request(self, "missing_sessionToken")
                    return
                if not check_session_rate_limit(token):
                    rate_limited(self)
                    return
                complete_session(token)
                json_response(self, 200, {"status": "ok", "score": session_score(token)})
                return
        except Exception:
            import traceback
            traceback.print_exc()
            try:
                json_response(self, 500, {"error": "internal_server_error"})
            except Exception:
                pass
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
            left_quality = score_decoy_quality(decoys["decoy_left"]["question"])
            right_quality = score_decoy_quality(decoys["decoy_right"]["question"])
            insert_question({
                "subject": subject,
                "difficulty": difficulty,
                "question": question_text,
                "options": options,
                "correct": correct_index,
                "decoy_left": decoys["decoy_left"],
                "decoy_right": decoys["decoy_right"],
                "decoy_left_quality": left_quality,
                "decoy_right_quality": right_quality
            })
            json_response(self, 200, {"status": "ok"})
            return

        if self.path == "/api/session/error":
            payload = parse_json(self)
            token = payload.get("sessionToken", "") if isinstance(payload, dict) else ""
            detail = json.dumps({
                "message": payload.get("message", "unknown_error") if isinstance(payload, dict) else "unknown_error",
                "stack": payload.get("stack", "") if isinstance(payload, dict) else ""
            })
            if token:
                record_event(token, "frontend_error", detail)
            json_response(self, 200, {"status": "ok"})
            return

        if self.path == "/api/admin/question/regenerate-decoys":
            if not require_admin(self):
                return
            payload = parse_json(self)
            question_id = require_number(payload, "questionId", 1)
            if question_id is None:
                bad_request(self, "invalid_questionId")
                return
            if not regenerate_question_decoys(int(question_id)):
                json_response(self, 404, {"error": "question_not_found"})
                return
            json_response(self, 200, {"status": "ok"})
            return

        if self.path.startswith("/api/admin/question/") and self.path.endswith("/regenerate-decoys"):
            if not require_admin(self):
                return
            parts = self.path.strip("/").split("/")
            try:
                question_id = int(parts[3])
            except Exception:
                bad_request(self, "invalid_questionId")
                return
            if not regenerate_question_decoys(question_id):
                json_response(self, 404, {"error": "question_not_found"})
                return
            json_response(self, 200, {"status": "ok"})
            return

        if self.path == "/api/admin/test-set":
            if not require_admin(self):
                return
            payload = parse_json(self)
            name = (payload.get("name") or "").strip()
            description = (payload.get("description") or "").strip()
            question_ids = payload.get("questionIds") or []
            time_limit_override = payload.get("timeLimitOverride")
            passing_threshold_override = payload.get("passingThresholdOverride")
            if not name or not question_ids:
                json_response(self, 400, {"error": "invalid_payload"})
                return
            set_id = create_test_set(
                name,
                description,
                question_ids,
                int(time_limit_override) if time_limit_override else None,
                float(passing_threshold_override) if passing_threshold_override else None
            )
            json_response(self, 200, {"id": set_id})
            return

        if self.path == "/api/admin/invite":
            if not require_admin(self):
                return
            payload = parse_json(self)
            set_id = (payload.get("setId") or "").strip()
            candidate_name = (payload.get("candidateName") or "").strip() or "Candidate"
            if not set_id:
                json_response(self, 400, {"error": "invalid_payload"})
                return
            token = create_invite(set_id, candidate_name)
            json_response(self, 200, {"token": token})
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

        if self.path == "/api/admin/session/note":
            if not require_admin(self):
                return
            payload = parse_json(self)
            token = require_string(payload, "token")
            note = require_string(payload, "note")
            if not token or not note:
                bad_request(self, "invalid_note_payload")
                return
            add_session_note(token, note)
            json_response(self, 200, {"status": "ok"})
            return

        json_response(self, 404, {"error": "not_found"})

    def do_GET(self):
        try:
            parsed = urlparse(self.path)
            path = parsed.path
            if path == "/" or path == "/index.html":
                serve_file(self, "index.html")
                return
            if path == "/test":
                serve_file(self, "index.html")
                return
            if path == "/admin" or path == "/admin.html":
                serve_file(self, "admin.html")
                return
            if path == "/styles.css":
                serve_file(self, "styles.css", "text/css; charset=utf-8")
                return
            if path == "/health":
                try:
                    questions = fetch_question_count()
                    db_status = "connected"
                except Exception:
                    questions = 0
                    db_status = "error"
                json_response(self, 200, {"status": "ok", "db": db_status, "questions": questions})
                return
            if path == "/api/local-access":
                ip = get_local_ip()
                json_response(self, 200, {"ip": ip, "url": f"http://{ip}:{PORT}/test"})
                return
            if path == "/api/admin/settings":
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
            if path == "/api/admin/sessions":
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
                    integrity = compute_integrity(answers, events)
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
                        "integrityScore": integrity,
                        "status": status,
                        "review": review
                    })
                json_response(self, 200, response)
                return
            if path.startswith("/api/admin/session/"):
                if not require_admin(self):
                    return
                token = path.split("/api/admin/session/", 1)[1]
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
                json_response(self, 200, {
                    "answers": response_answers,
                    "events": response_events,
                    "review": review,
                    "notes": [
                        {"note": n["note"], "createdAt": n["created_at"]} for n in list_session_notes(token)
                    ],
                    "integrityScore": compute_integrity(answers, events)
                })
                return
            if path == "/api/admin/live-sessions":
                if not require_admin(self):
                    return
                response = []
                for row in list_sessions():
                    if row["completed_at"] is not None:
                        continue
                    answers = list_session_answers(row["token"])
                    compliance = (sum(a["head_compliance"] for a in answers) / len(answers)) if answers else 1
                    response.append({
                        "token": row["token"],
                        "name": row["name"],
                        "currentQuestion": len(answers) + 1,
                        "elapsedSec": int(time.time()) - row["started_at"],
                        "headCompliance": compliance
                    })
                json_response(self, 200, response)
                return
            if path == "/api/admin/sessions/live":
                if not require_admin(self):
                    return
                response = []
                for row in list_sessions():
                    if row["completed_at"] is not None:
                        continue
                    answers = list_session_answers(row["token"])
                    compliance = (sum(a["head_compliance"] for a in answers) / len(answers)) if answers else 1
                    response.append({
                        "token": row["token"],
                        "name": row["name"],
                        "currentQuestion": len(answers) + 1,
                        "elapsedSec": int(time.time()) - row["started_at"],
                        "headCompliance": compliance
                    })
                json_response(self, 200, response)
                return
            if path == "/api/admin/questions":
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
                            "options": json.loads(row["decoy_left_options_json"]),
                            "quality": row["decoy_left_quality"]
                        },
                        "decoyRight": {
                            "question": row["decoy_right_text"],
                            "options": json.loads(row["decoy_right_options_json"]),
                            "quality": row["decoy_right_quality"]
                        }
                    })
                json_response(self, 200, response)
                return
            if path == "/api/admin/decoy-audit":
                if not require_admin(self):
                    return
                json_response(self, 200, decoy_audit_rows())
                return
            if path == "/api/admin/test-sets":
                if not require_admin(self):
                    return
                out = []
                for item in list_test_sets():
                    invites = []
                    for invite in item["invites"]:
                        answers = list_session_answers(invite["session_token"]) if invite["session_token"] else []
                        total = len(answers)
                        correct = sum(1 for a in answers if a["correct"] == 1)
                        invites.append({
                            "token": invite["token"],
                            "candidateName": invite["candidate_name"],
                            "status": invite["status"],
                            "score": (correct / total) if total else 0
                        })
                    out.append({
                        "id": item["set"]["id"],
                        "name": item["set"]["name"],
                        "description": item["set"]["description"],
                        "timeLimitOverride": item["set"]["time_limit_override"],
                        "passingThresholdOverride": item["set"]["passing_threshold_override"],
                        "questionIds": [q["question_id"] for q in item["questions"]],
                        "invites": invites
                    })
                json_response(self, 200, out)
                return
            if path == "/api/admin/sessions/export":
                if not require_admin(self):
                    return
                rows = ["candidate name,date,score,integrity score,time taken,flagged events count"]
                flagged_types = {"tab_hidden", "window_blur", "right_click", "devtools_open", "face_lost", "clipboard_attempt", "liveness_fail", "screen_capture_attempt"}
                for row in list_sessions():
                    if row["completed_at"] is None:
                        continue
                    answers = list_session_answers(row["token"])
                    events = list_session_events(row["token"])
                    total = len(answers)
                    correct = sum(1 for a in answers if a["correct"] == 1)
                    score = int(round((correct / total) * 100)) if total else 0
                    integrity = compute_integrity(answers, events)
                    flagged = sum(1 for e in events if e["event_type"] in flagged_types)
                    duration = int(row["completed_at"]) - int(row["started_at"])
                    safe_name = '"' + str(row["name"]).replace('"', '""') + '"'
                    rows.append(
                        f'{safe_name},{time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(row["started_at"])))},{score},{integrity},{duration},{flagged}'
                    )
                send_text(self, 200, "\n".join(rows), "text/csv; charset=utf-8")
                return
            if path.startswith("/api/invite/"):
                token = path.split("/api/invite/", 1)[1]
                invite = fetch_invite(token)
                if not invite:
                    json_response(self, 404, {"error": "not_found"})
                    return
                json_response(self, 200, {
                    "token": invite["token"],
                    "candidateName": invite["candidate_name"],
                    "status": invite["status"],
                    "setId": invite["set_id"]
                })
                return
            if path == "/api/session/status":
                token = parsed.query.split("token=", 1)[1] if "token=" in parsed.query else ""
                if not token:
                    bad_request(self, "missing_token")
                    return
                meta = None
                with DB_LOCK:
                    conn = db_connect()
                    try:
                        meta = conn.execute("SELECT started_at, completed_at FROM session_meta WHERE token = ?", (token,)).fetchone()
                    finally:
                        conn.close()
                if not meta:
                    json_response(self, 404, {"error": "session_not_found"})
                    return
                json_response(self, 200, {"status": "complete" if meta["completed_at"] else "in_progress", "expired": False})
                return
            if path == "/api/session/result":
                token = parsed.query.split("token=", 1)[1] if "token=" in parsed.query else ""
                if not token:
                    bad_request(self, "missing_token")
                    return
                answers = list_session_answers(token)
                meta = None
                with DB_LOCK:
                    conn = db_connect()
                    try:
                        meta = conn.execute("SELECT started_at, completed_at FROM session_meta WHERE token = ?", (token,)).fetchone()
                    finally:
                        conn.close()
                total = len(answers)
                correct = sum(1 for a in answers if a["correct"] == 1)
                passing = float(get_setting("passing_threshold", "0.7"))
                score = (correct / total) if total else 0
                time_taken_ms = int(((meta["completed_at"] or int(time.time())) - meta["started_at"]) * 1000) if meta else 0
                json_response(self, 200, {
                    "score": correct,
                    "total": total,
                    "passed": score >= passing,
                    "timeTakenMs": time_taken_ms,
                    "passingThreshold": passing
                })
                return
            json_response(self, 404, {"error": "not_found"})
            return
        except Exception:
            import traceback
            traceback.print_exc()
            try:
                json_response(self, 500, {"error": "internal_server_error"})
            except Exception:
                pass
            return

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
