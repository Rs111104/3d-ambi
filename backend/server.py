import os
import json
import time
import logging
import traceback
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import db
import auth
import logic
from config import Config

# Advanced Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("3d-ambi")

class AmbiRequestHandler(BaseHTTPRequestHandler):
    """Secure request handler for 3D Ambi API and static assets."""
    
    def send_json(self, status: int, data: dict):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-CSRF-Token")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def do_OPTIONS(self):
        self.send_response(204); self.end_headers()

    def check_auth(self, req_csrf: bool = False) -> bool:
        """Validates Bearer token and optional CSRF token."""
        h = self.headers.get("Authorization", "")
        if not h.startswith("Bearer "): 
            # Fallback for SSE
            t = parse_qs(urlparse(self.path).query).get("token", [""])[0]
            if t and auth.verify_admin_token(t): return True
            self.send_json(401, {"error": "unauthorized"}); return False
        
        token = h[7:]
        if not auth.verify_admin_token(token):
            self.send_json(401, {"error": "unauthorized"}); return False
        
        if req_csrf:
            ct = self.headers.get("X-CSRF-Token", "")
            if not auth.verify_csrf_token(token, ct):
                self.send_json(403, {"error": "invalid_csrf"}); return False
        return True

    def do_GET(self):
        try:
            p = urlparse(self.path).path
            q = parse_qs(urlparse(self.path).query)

            # --- Public Endpoints ---
            if p == "/": p = "/index.html"
            if p.endswith(".html") or p.endswith(".css"):
                self.serve_static(p); return

            # --- Admin API ---
            if p.startswith("/api/admin/"):
                if not self.check_auth(): return
                
                if p == "/api/admin/sessions":
                    with db.DB_LOCK:
                        conn = db.db_connect()
                        rows = conn.execute("SELECT m.*, s.integrity_score, (SELECT SUM(correct)*1.0/COUNT(*) FROM session_answers WHERE token=m.token) as score FROM session_meta m LEFT JOIN sessions s ON s.token=m.token ORDER BY m.started_at DESC").fetchall()
                        res = [dict(r) for r in rows]
                        for r in res: r["durationSec"] = (r["completed_at"] - r["started_at"]) if r["completed_at"] else (int(time.time()) - r["started_at"])
                        self.send_json(200, res); conn.close(); return

                if p.startswith("/api/admin/session/"):
                    token = p.split("/")[-1]
                    with db.DB_LOCK:
                        conn = db.db_connect()
                        evts = conn.execute("SELECT * FROM session_events WHERE token=? ORDER BY created_at ASC", (token,)).fetchall()
                        ans = conn.execute("SELECT a.*, q.question_text FROM session_answers a JOIN questions q ON q.id=a.question_id WHERE a.token=?", (token,)).fetchall()
                        self.send_json(200, {"events": [dict(e) for e in evts], "answers": [dict(a) for a in ans]})
                        conn.close(); return

                if p == "/api/admin/questions":
                    with db.DB_LOCK:
                        conn = db.db_connect(); rows = conn.execute("SELECT * FROM questions ORDER BY id DESC").fetchall()
                        self.send_json(200, [dict(r) for r in rows]); conn.close(); return

            self.send_error(404)
        except Exception:
            logger.error(traceback.format_exc()); self.send_error(500)

    def do_POST(self):
        try:
            cl = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(cl).decode('utf-8')
            data = json.loads(body) if body else {}
            p = urlparse(self.path).path

            # --- Public Auth ---
            if p == "/api/admin/login":
                res = auth.authenticate_admin(data.get("username"), data.get("password"))
                if res: self.send_json(200, {"token": res[0], "csrfToken": res[1]})
                else: self.send_json(401, {"error": "unauthorized"})
                return

            # --- Candidate Assessment ---
            if p == "/api/session/start":
                tok = logic.create_session(data.get("name", "Anonymous"))
                self.send_json(200, {"sessionToken": tok}); return

            if p == "/api/session/next":
                tok = data.get("sessionToken"); s = logic.get_session(tok)
                if not s: self.send_json(404, {"error": "not_found"}); return
                
                idx = s["next_index"]; order = json.loads(s["question_order_json"])
                if idx >= len(order): self.send_json(400, {"error": "complete"}); return
                
                with db.DB_LOCK:
                    conn = db.db_connect(); q = conn.execute("SELECT * FROM questions WHERE id=?", (order[idx],)).fetchone(); conn.close()
                
                payload = {
                    "questionId": q["id"], "question": q["question_text"], "options": json.loads(q["options_json"]), "totalQuestions": len(order),
                    "decoyLeft": {"question": q["decoy_left_text"] or "Decoy", "options": []},
                    "decoyRight": {"question": q["decoy_right_text"] or "Decoy", "options": []}
                }
                enc = logic.encrypt_data(payload, logic.derive_session_key(tok))
                self.send_json(200, {**enc, "questionId": q["id"], "totalQuestions": len(order)}); return

            if p == "/api/session/answer":
                ok, msg = logic.record_answer(data.get("sessionToken"), data.get("questionId"), data.get("answerIndex"), data.get("timeMs"), data.get("headCompliance"), data.get("proof"))
                self.send_json(200 if ok else 400, {"status": "ok" if ok else msg}); return

            self.send_error(404)
        except Exception:
            logger.error(traceback.format_exc()); self.send_error(500)

    def serve_static(self, p: str):
        """Serves frontend files from the workspace."""
        try:
            # Determine correct path
            root = os.path.dirname(os.path.dirname(__file__))
            fpath = os.path.join(root, "frontend", p.lstrip("/"))
            if not os.path.exists(fpath): self.send_error(404); return
            
            with open(fpath, "rb") as f:
                self.send_response(200)
                if p.endswith(".html"): self.send_header("Content-Type", "text/html")
                if p.endswith(".css"): self.send_header("Content-Type", "text/css")
                self.end_headers(); self.wfile.write(f.read())
        except Exception: self.send_error(500)

def run():
    db.init_db()
    # Seed default admin
    with db.DB_LOCK:
        conn = db.db_connect()
        if not conn.execute("SELECT id FROM admin_users WHERE username=?", (Config.ADMIN_USER,)).fetchone():
            h, s = auth.hash_password(Config.ADMIN_PASS)
            conn.execute("INSERT INTO admin_users (username, password_hash, salt, created_at) VALUES (?,?,?,?)", (Config.ADMIN_USER, h, s, int(time.time())))
            conn.commit(); conn.close()
            
    server = ThreadingHTTPServer(('', Config.PORT), AmbiRequestHandler)
    logger.info(f"🚀 3D Ambi Server active on port {Config.PORT}")
    server.serve_forever()

if __name__ == "__main__":
    run()
