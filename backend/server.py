import os
import json
import time
import logging
import traceback
import socket
import csv
import io
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import db
import auth
import logic
from config import Config

# High-fidelity logging for system monitoring
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger("3D-Ambi")

class AmbiRequestHandler(BaseHTTPRequestHandler):
    """Secure request handler for 3D Ambi API and high-performance static asset delivery."""
    
    def send_json(self, status: int, data: dict):
        """Standardized JSON response with security and CORS headers."""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-CSRF-Token")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def do_OPTIONS(self):
        """Handle CORS pre-flight requests."""
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-CSRF-Token")
        self.end_headers()

    def validate_administrative_session(self, require_csrf: bool = False) -> bool:
        """Verifies Bearer token and optional CSRF state for administrative actions."""
        auth_header = self.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            # Allow query-string token for SSE and exports
            token = parse_qs(urlparse(self.path).query).get("token", [""])[0]
            if token and auth.verify_admin_token(token): return True
            self.send_json(401, {"error": "Unauthorized session"}); return False
        
        token = auth_header[7:]
        if not auth.verify_admin_token(token):
            self.send_json(401, {"error": "Session expired"}); return False
        
        if require_csrf and not auth.verify_csrf_token(token, self.headers.get("X-CSRF-Token", "")):
            self.send_json(403, {"error": "Security validation failure (CSRF)"}); return False
        return True

    def do_GET(self):
        """Route read-only requests to static assets or administrative data providers."""
        try:
            url = urlparse(self.path); path = url.path
            
            # --- Static Asset Pipeline ---
            if path == "/": path = "/index.html"
            if path.endswith((".html", ".css", ".js", ".png", ".jpg", ".ico")):
                self.serve_static_file(path); return

            # --- Administrative Intelligence API ---
            if path.startswith("/api/admin/"):
                if not self.validate_administrative_session(): return
                
                if path == "/api/admin/sessions":
                    with db.DB_LOCK:
                        conn = db.db_connect()
                        rows = conn.execute("SELECT m.*, s.integrity_score, (SELECT SUM(correct)*1.0/COUNT(*) FROM session_answers WHERE token=m.token) as score FROM session_meta m LEFT JOIN sessions s ON s.token=m.token ORDER BY m.started_at DESC").fetchall()
                        sessions = [dict(r) for r in rows]
                        for s in sessions: s["durationSec"] = (s["completed_at"] or int(time.time())) - s["started_at"]
                        self.send_json(200, sessions); conn.close(); return

                if path.startswith("/api/admin/session/"):
                    token = path.split("/")[-1]
                    with db.DB_LOCK:
                        conn = db.db_connect()
                        events = conn.execute("SELECT * FROM session_events WHERE token=? ORDER BY created_at ASC", (token,)).fetchall()
                        answers = conn.execute("SELECT a.*, q.question_text FROM session_answers a JOIN questions q ON q.id=a.question_id WHERE a.token=?", (token,)).fetchall()
                        self.send_json(200, {"events": [dict(e) for e in events], "answers": [dict(a) for a in answers]})
                        conn.close(); return

                if path == "/api/admin/questions":
                    with db.DB_LOCK:
                        conn = db.db_connect(); rows = conn.execute("SELECT * FROM questions ORDER BY id DESC").fetchall()
                        self.send_json(200, [dict(r) for r in rows]); conn.close(); return

                if path == "/api/admin/sessions/export":
                    with db.DB_LOCK:
                        conn = db.db_connect(); rows = conn.execute("SELECT m.name, m.started_at, m.completed_at, s.integrity_score FROM session_meta m LEFT JOIN sessions s ON s.token=m.token").fetchall(); conn.close()
                    out = io.StringIO(); w = csv.writer(out); w.writerow(["Candidate", "Start", "End", "Integrity"])
                    for r in rows: w.writerow([r[0], time.ctime(r[1]), time.ctime(r[2]) if r[2] else "Active", r[3]])
                    self.send_response(200); self.send_header("Content-Type", "text/csv"); self.send_header("Content-Disposition", "attachment; filename=3d_ambi_sessions.csv"); self.end_headers(); self.wfile.write(out.getvalue().encode("utf-8")); return

            self.send_error(404)
        except Exception: logger.error(traceback.format_exc()); self.send_error(500)

    def do_POST(self):
        """Route state-modifying requests to auth or session controllers."""
        try:
            cl = int(self.headers.get('Content-Length', 0)); body = json.loads(self.rfile.read(cl).decode('utf-8')) if cl else {}
            path = urlparse(self.path).path

            if path == "/api/admin/login":
                res = auth.authenticate_admin(body.get("username"), body.get("password"))
                if res: self.send_json(200, {"token": res[0], "csrfToken": res[1]})
                else: self.send_json(401, {"error": "Invalid credentials"})
                return

            if path == "/api/session/start":
                self.send_json(200, {"sessionToken": logic.create_session(body.get("name", "Anonymous Candidate"))}); return

            if path == "/api/session/next":
                tok = body.get("sessionToken"); s = logic.get_session(tok)
                if not s: self.send_json(404, {"error": "invalid_session"}); return
                idx = s["next_index"]; order = json.loads(s["question_order_json"])
                if idx >= len(order): self.send_json(400, {"error": "assessment_complete"}); return
                with db.DB_LOCK:
                    conn = db.db_connect(); q = conn.execute("SELECT * FROM questions WHERE id=?", (order[idx],)).fetchone(); conn.close()
                payload = {"questionId": q["id"], "question": q["question_text"], "options": json.loads(q["options_json"]), "totalQuestions": len(order), "decoyLeft": {"question": q["decoy_left_text"], "options": []}, "decoyRight": {"question": q["decoy_right_text"], "options": []}}
                enc = logic.encrypt_data(payload, logic.derive_session_key(tok))
                self.send_json(200, {**enc, "questionId": q["id"], "totalQuestions": len(order)}); return

            if path == "/api/session/answer":
                ok, msg = logic.record_answer(body.get("sessionToken"), body.get("questionId"), body.get("answerIndex"), body.get("timeMs"), body.get("headCompliance"), body.get("proof"))
                self.send_json(200 if ok else 400, {"status": "ok" if ok else msg}); return

            if path == "/api/session/event":
                logic.record_event(body.get("sessionToken"), body.get("type"), body.get("detail"))
                self.send_json(200, {"status": "recorded"}); return

            # --- Administrative Command API ---
            if path.startswith("/api/admin/"):
                if not self.validate_administrative_session(require_csrf=True): return
                if path == "/api/admin/question":
                    with db.DB_LOCK:
                        conn = db.db_connect()
                        conn.execute("INSERT INTO questions (subject, question_text, options_json, correct_index, decoy_left_text, decoy_right_text, created_at) VALUES (?,?,?,?,?,?,?)",
                                     (body["subject"], body["question"], json.dumps(body["options"]), body["correctIndex"], body["decoyLeft"], body["decoyRight"], int(time.time())))
                        conn.commit(); conn.close()
                    self.send_json(200, {"status": "ok"}); return

            self.send_error(404)
        except Exception: logger.error(traceback.format_exc()); self.send_error(500)

    def serve_static_file(self, path: str):
        """Safely stream assets from the localized frontend store."""
        try:
            root = os.path.dirname(os.path.dirname(__file__))
            fpath = os.path.join(root, "frontend", path.lstrip("/"))
            if not os.path.exists(fpath): self.send_error(404); return
            with open(fpath, "rb") as f:
                self.send_response(200)
                if path.endswith(".html"): self.send_header("Content-Type", "text/html")
                elif path.endswith(".css"): self.send_header("Content-Type", "text/css")
                elif path.endswith(".js"): self.send_header("Content-Type", "application/javascript")
                self.end_headers(); self.wfile.write(f.read())
        except Exception: self.send_error(500)

if __name__ == "__main__":
    db.init_db()
    # Seed identity if required
    with db.DB_LOCK:
        conn = db.db_connect()
        if not conn.execute("SELECT id FROM admin_users WHERE username=?", (Config.ADMIN_USER,)).fetchone():
            h, s = auth.hash_password(Config.ADMIN_PASS)
            conn.execute("INSERT INTO admin_users (username, password_hash, salt, created_at) VALUES (?,?,?,?)", (Config.ADMIN_USER, h, s, int(time.time())))
            conn.commit(); conn.close()
    
    server = ThreadingHTTPServer(('', Config.PORT), AmbiRequestHandler)
    logger.info(f"💎 3D Ambi Engine ready at http://localhost:{Config.PORT}")
    server.serve_forever()
