import sys
import os
import secrets
import time
import json
import logging
import bcrypt
import io
import csv
from flask import Flask, request, jsonify, send_from_directory, redirect, abort, make_response
from functools import wraps
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

import db

# Structured JSON Logging
class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            "ts": self.formatTime(record),
            "level": record.levelname,
            "msg": record.getMessage(),
            "logger": record.name,
        }
        if hasattr(record, "extra"):
            log_entry.update(record.extra)
        return json.dumps(log_entry)

handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logging.basicConfig(level=logging.INFO, handlers=[handler])
logger = logging.getLogger("3d-ambigram")

def _require_env(key: str) -> str:
    val = os.environ.get(key)
    if not val:
        print(f"FATAL: environment variable '{key}' is not set.", file=sys.stderr)
        sys.exit(1)
    return val

# Critical security checks at startup
ADMIN_USER = _require_env("ADMIN_USER")
ADMIN_PASSWORD_HASH = _require_env("ADMIN_PASSWORD_HASH")
FLASK_SECRET = _require_env("FLASK_SECRET")

app = Flask(__name__, static_folder="../frontend")
app.secret_key = FLASK_SECRET

# Rate Limiter
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        token = request.cookies.get("admin_token")
        if not token:
            if request.path.startswith("/api/"):
                return jsonify({"error": "unauthorized"}), 401
            return redirect("/admin/login")
        with db.get_db() as cx:
            row = cx.execute(
                "SELECT created_at FROM admin_sessions WHERE token=?", (token,)
            ).fetchone()
        if not row or time.time() - row[0] > 3600:
            if request.path.startswith("/api/"):
                return jsonify({"error": "session expired"}), 401
            return redirect("/admin/login")
        return f(*args, **kwargs)
    return wrapper

@app.before_request
def check_csrf_header():
    if request.method in ("POST", "PATCH", "DELETE"):
        if request.content_type == "application/json":
            if request.headers.get("X-Requested-With") != "XMLHttpRequest":
                abort(403)

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/admin")
@admin_required
def admin_dashboard():
    return send_from_directory(app.static_folder, "admin.html")

@app.route("/admin/login", methods=["GET"])
def admin_login_page():
    return send_from_directory(app.static_folder, "admin.html")

@app.route("/api/admin/login", methods=["POST"])
@limiter.limit("5 per minute")
def admin_login():
    body = request.get_json(silent=True) or {}
    u = body.get("username", "")
    p = body.get("password", "")
    
    if u != ADMIN_USER or not bcrypt.checkpw(p.encode(), ADMIN_PASSWORD_HASH.encode()):
        logger.warning("failed admin login attempt", extra={"user": u})
        return jsonify({"error": "invalid credentials"}), 401
    
    token = secrets.token_urlsafe(32)
    with db.get_db() as cx:
        cx.execute("INSERT INTO admin_sessions (token, created_at) VALUES (?,?)", (token, time.time()))
        cx.commit()
    
    logger.info("admin login successful", extra={"user": u})
    resp = jsonify({"ok": True})
    resp.set_cookie("admin_token", token, httponly=True,
                    samesite="Strict", secure=True, max_age=3600)
    return resp

@app.route("/api/session/start", methods=["POST"])
@limiter.limit("3 per 10 minutes")
def start_session():
    sid = secrets.token_urlsafe(32)
    db.session_upsert(sid, started_at=time.time())
    logger.info("session started", extra={"session_id": sid})
    resp = jsonify({"ok": True, "session_id": sid})
    resp.set_cookie("session_id", sid, httponly=True, samesite="Strict", secure=True)
    return resp

@app.route("/api/session/consent", methods=["POST"])
def session_consent():
    sid = request.cookies.get("session_id")
    if not db.session_get(sid):
        return jsonify({"error": "unauthorized"}), 403
    db.session_upsert(sid, consented_at=time.time())
    return jsonify({"ok": True})

@app.route("/api/question", methods=["GET"])
def get_question():
    sid = request.cookies.get("session_id")
    sess = db.session_get(sid)
    if not sess:
        return jsonify({"error": "unauthorized"}), 403
    
    idx = sess["q"]
    with db.get_db() as cx:
        questions = cx.execute("SELECT id, text, options FROM questions ORDER BY id").fetchall()
    
    if idx >= len(questions):
        db.session_upsert(sid, finished_at=time.time())
        return jsonify({"done": True})
    
    q = questions[idx]
    return jsonify({
        "id": q["id"],
        "text": q["text"],
        "options": json.loads(q["options"]),
        "index": idx,
        "total": len(questions)
    })

@app.route("/api/decoy", methods=["GET"])
def get_decoy():
    sid = request.cookies.get("session_id")
    if not db.session_get(sid):
        abort(403)
    db.log_flag(sid, "decoy_requested")
    return jsonify({
        "text": "Which planet is closest to the Sun?",
        "options": ["Venus", "Mercury", "Earth", "Mars"]
    })

@app.route("/api/answer", methods=["POST"])
def submit_answer():
    sid = request.cookies.get("session_id")
    sess = db.session_get(sid)
    if not sess:
        return jsonify({"error": "unauthorized"}), 403
    
    body = request.get_json(silent=True) or {}
    q_id = body.get("questionId")
    answer = body.get("answer")
    
    answers = sess["answers"]
    answers[str(q_id)] = answer
    
    db.session_upsert(sid, current_q=sess["q"] + 1, answers=json.dumps(answers))
    return jsonify({"ok": True})

@app.route("/api/flag", methods=["POST"])
def log_event():
    sid = request.cookies.get("session_id")
    if not sid:
        return jsonify({"error": "unauthorized"}), 403
    
    body = request.get_json(silent=True) or {}
    event_type = body.get("type")
    detail = body.get("detail")
    duration = body.get("duration_ms")
    
    db.log_flag(sid, event_type, detail, duration)
    logger.warning("flag event", extra={"session_id": sid, "type": event_type, "detail": detail})
    
    # Simple integrity penalty
    with db.get_db() as cx:
        cx.execute("UPDATE sessions SET integrity_score = MAX(0, integrity_score - 10) WHERE id=?", (sid,))
        cx.commit()
        
    return jsonify({"ok": True})

# --- Admin API ---

@app.route("/api/admin/sessions", methods=["GET"])
@admin_required
def admin_sessions():
    with db.get_db() as cx:
        rows = cx.execute("SELECT * FROM sessions ORDER BY started_at DESC").fetchall()
    sessions = []
    for r in rows:
        sessions.append({
            "id": r["id"],
            "token": r["id"],
            "name": r["candidate_email"] or "Anonymous",
            "started_at": r["started_at"],
            "durationSec": (r["finished_at"] or time.time()) - r["started_at"],
            "score": 0.0,
            "integrity_score": r["integrity_score"]
        })
    return jsonify(sessions)

@app.route("/api/admin/session/<sid>", methods=["GET"])
@admin_required
def admin_session_detail(sid):
    with db.get_db() as cx:
        events = cx.execute("SELECT * FROM flag_events WHERE session_id=? ORDER BY ts ASC", (sid,)).fetchall()
    return jsonify({
        "events": [{
            "type": e["event_type"],
            "detail": e["detail"],
            "created_at": e["ts"]
        } for e in events]
    })

@app.route("/api/admin/questions", methods=["GET"])
@admin_required
def admin_questions():
    with db.get_db() as cx:
        rows = cx.execute("SELECT * FROM questions ORDER BY id").fetchall()
    return jsonify([dict(r) for r in rows])

@app.route("/api/admin/question", methods=["POST"])
@admin_required
def add_question():
    body = request.get_json()
    with db.get_db() as cx:
        cx.execute("INSERT INTO questions (text, options) VALUES (?,?)",
                   (body["question"], json.dumps(body["options"])))
        cx.commit()
    return jsonify({"ok": True})

@app.route("/api/admin/sessions/export", methods=["GET"])
@admin_required
def export_sessions():
    with db.get_db() as cx:
        rows = cx.execute("SELECT * FROM sessions").fetchall()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Name", "Started At", "Finished At", "Integrity"])
    for r in rows:
        writer.writerow([r["id"], r["candidate_email"] or "Anonymous", 
                         time.ctime(r["started_at"]), 
                         time.ctime(r["finished_at"]) if r["finished_at"] else "Active",
                         r["integrity_score"]])
    
    resp = make_response(output.getvalue())
    resp.headers["Content-Disposition"] = "attachment; filename=sessions.csv"
    resp.headers["Content-Type"] = "text/csv"
    return resp

@app.route("/<path:path>")
def static_proxy(path):
    return send_from_directory(app.static_folder, path)

if __name__ == "__main__":
    db.init_db()
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
