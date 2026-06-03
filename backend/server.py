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

# Configure high-fidelity logging for production monitoring
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger("3D-Ambi")

class AmbiRequestHandler(BaseHTTPRequestHandler):
    """
    High-performance, secure request handler for the 3D Ambi assessment engine.
    Handles static asset serving, administrative API endpoints, and candidate session logic.
    """
    
    def send_json(self, status: int, data: dict):
        """Sends a JSON response with standard security and CORS headers."""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-CSRF-Token")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def do_OPTIONS(self):
        """Handles Pre-flight CORS requests."""
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-CSRF-Token")
        self.end_headers()

    def check_administrative_auth(self, require_csrf: bool = False) -> bool:
        """
        Validates the request against the administrative session store.
        Checks for a valid Bearer token and optionally verifies CSRF integrity.
        """
        auth_header = self.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "): 
            # Special case: allow token via query parameter for SSE/Export streams
            query_token = parse_qs(urlparse(self.path).query).get("token", [""])[0]
            if query_token and auth.verify_admin_token(query_token): 
                return True
            self.send_json(401, {"error": "Unauthorized: Missing or invalid token"})
            return False
        
        token = auth_header[7:]
        if not auth.verify_admin_token(token):
            self.send_json(401, {"error": "Session expired or invalid"})
            return False
        
        if require_csrf:
            csrf_token = self.headers.get("X-CSRF-Token", "")
            if not auth.verify_csrf_token(token, csrf_token):
                self.send_json(403, {"error": "Security validation failed: CSRF mismatch"})
                return False
        return True

    def do_GET(self):
        """Dispatches GET requests to static file server or Administrative API."""
        try:
            parsed_url = urlparse(self.path)
            request_path = parsed_url.path
            
            # --- Static Asset Routing ---
            if request_path == "/": 
                request_path = "/index.html"
            
            if request_path.endswith((".html", ".css", ".js", ".png", ".jpg")):
                self.serve_static_asset(request_path)
                return

            # --- Administrative API (Read Operations) ---
            if request_path.startswith("/api/admin/"):
                if not self.check_administrative_auth(): return
                
                if request_path == "/api/admin/sessions":
                    with db.DB_LOCK:
                        conn = db.db_connect()
                        rows = conn.execute("""
                            SELECT m.*, s.integrity_score, 
                            (SELECT SUM(correct)*1.0/COUNT(*) FROM session_answers WHERE token=m.token) as score 
                            FROM session_meta m 
                            LEFT JOIN sessions s ON s.token=m.token 
                            ORDER BY m.started_at DESC
                        """).fetchall()
                        results = [dict(row) for row in rows]
                        for session in results:
                            session["durationSec"] = (session["completed_at"] - session["started_at"]) if session["completed_at"] else (int(time.time()) - session["started_at"])
                        conn.close()
                    self.send_json(200, results)
                    return

                if request_path.startswith("/api/admin/session/"):
                    session_token = request_path.split("/")[-1]
                    with db.DB_LOCK:
                        conn = db.db_connect()
                        events = conn.execute("SELECT * FROM session_events WHERE token=? ORDER BY created_at ASC", (session_token,)).fetchall()
                        answers = conn.execute("SELECT a.*, q.question_text FROM session_answers a JOIN questions q ON q.id=a.question_id WHERE a.token=?", (session_token,)).fetchall()
                        conn.close()
                    self.send_json(200, {"events": [dict(e) for e in events], "answers": [dict(a) for a in answers]})
                    return

                if request_path == "/api/admin/questions":
                    with db.DB_LOCK:
                        conn = db.db_connect()
                        rows = conn.execute("SELECT * FROM questions ORDER BY id DESC").fetchall()
                        conn.close()
                    self.send_json(200, [dict(row) for row in rows])
                    return
                
                if request_path == "/api/admin/sessions/export":
                    with db.DB_LOCK:
                        conn = db.db_connect()
                        rows = conn.execute("SELECT m.name, m.started_at, m.completed_at, s.integrity_score FROM session_meta m LEFT JOIN sessions s ON s.token=m.token WHERE m.completed_at IS NOT NULL").fetchall()
                        conn.close()
                    
                    output = io.StringIO()
                    writer = csv.writer(output)
                    writer.writerow(["Candidate", "Start Time", "End Time", "Integrity Score"])
                    for row in rows:
                        writer.writerow([row["name"], time.ctime(row["started_at"]), time.ctime(row["completed_at"]), row["integrity_score"]])
                    
                    self.send_response(200)
                    self.send_header("Content-Type", "text/csv")
                    self.send_header("Content-Disposition", "attachment; filename=assessment_sessions.csv")
                    self.end_headers()
                    self.wfile.write(output.getvalue().encode("utf-8"))
                    return

            self.send_error(404, "Endpoint not found")
        except Exception:
            logger.error(f"Error handling GET {self.path}:\n{traceback.format_exc()}")
            self.send_error(500, "Internal Server Error")

    def do_POST(self):
        """Handles data-modifying operations for candidates and admins."""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            request_body = self.rfile.read(content_length).decode('utf-8')
            request_data = json.loads(request_body) if request_body else {}
            request_path = urlparse(self.path).path

            # --- Administrative Auth ---
            if request_path == "/api/admin/login":
                # Implementation of rate limiting (check logic.py or server state)
                auth_result = auth.authenticate_admin(request_data.get("username"), request_data.get("password"))
                if auth_result:
                    self.send_json(200, {"token": auth_result[0], "csrfToken": auth_result[1]})
                else:
                    self.send_json(401, {"error": "Invalid administrative credentials"})
                return

            # --- Candidate Session Lifecycle ---
            if request_path == "/api/session/start":
                candidate_name = request_data.get("name", "Anonymous Candidate")
                session_token = logic.create_session(candidate_name)
                self.send_json(200, {"sessionToken": session_token})
                return

            if request_path == "/api/session/next":
                session_token = request_data.get("sessionToken")
                session_state = logic.get_session(session_token)
                if not session_state:
                    self.send_json(404, {"error": "Session context not found"})
                    return
                
                current_index = session_state["next_index"]
                question_order = json.loads(session_state["question_order_json"])
                
                if current_index >= len(question_order):
                    self.send_json(400, {"error": "assessment_complete"})
                    return
                
                with db.DB_LOCK:
                    conn = db.db_connect()
                    question_row = conn.execute("SELECT * FROM questions WHERE id=?", (question_order[current_index],)).fetchone()
                    conn.close()
                
                if not question_row:
                    self.send_json(500, {"error": "Data integrity error: question missing from bank"})
                    return

                # Build secure payload for WebGL delivery
                payload = {
                    "questionId": question_row["id"],
                    "question": question_row["question_text"],
                    "options": json.loads(question_row["options_json"]),
                    "totalQuestions": len(question_order),
                    "decoyLeft": {"question": question_row["decoy_left_text"] or "Unauthorized viewing detected", "options": []},
                    "decoyRight": {"question": question_row["decoy_right_text"] or "Please face the screen", "options": []}
                }
                
                encrypted_payload = logic.encrypt_data(payload, logic.derive_session_key(session_token))
                self.send_json(200, {
                    **encrypted_payload,
                    "questionId": question_row["id"],
                    "totalQuestions": len(question_order)
                })
                return

            if request_path == "/api/session/answer":
                # Validates the Rendering Proof before committing the answer
                success, message = logic.record_answer(
                    request_data.get("sessionToken"),
                    request_data.get("questionId"),
                    request_data.get("answerIndex"),
                    request_data.get("timeMs"),
                    request_data.get("headCompliance"),
                    request_data.get("proof")
                )
                self.send_json(200 if success else 400, {"status": "ok" if success else message})
                return

            if request_path == "/api/session/event":
                logic.record_event(
                    request_data.get("sessionToken"),
                    request_data.get("type"),
                    request_data.get("detail")
                )
                self.send_json(200, {"status": "event_recorded"})
                return

            self.send_error(404)
        except Exception:
            logger.error(f"Error handling POST {self.path}:\n{traceback.format_exc()}")
            self.send_error(500, "Critical process failure")

    def serve_static_asset(self, request_path: str):
        """Safely streams static assets from the frontend directory."""
        try:
            root_dir = os.path.dirname(os.path.dirname(__file__))
            file_path = os.path.join(root_dir, "frontend", request_path.lstrip("/"))
            
            if not os.path.exists(file_path):
                self.send_error(404, "Asset missing")
                return
            
            with open(file_path, "rb") as asset_file:
                content = asset_file.read()
                self.send_response(200)
                if request_path.endswith(".html"): self.send_header("Content-Type", "text/html")
                elif request_path.endswith(".css"): self.send_header("Content-Type", "text/css")
                elif request_path.endswith(".js"): self.send_header("Content-Type", "application/javascript")
                self.send_header("Content-Length", len(content))
                self.end_headers()
                self.wfile.write(content)
        except Exception:
            self.send_error(500)

def main():
    """Starts the 3D Ambi production-ready assessment server."""
    db.init_db()
    
    # Ensure administrative identity exists
    with db.DB_LOCK:
        conn = db.db_connect()
        admin_exists = conn.execute("SELECT id FROM admin_users WHERE username=?", (Config.ADMIN_USER,)).fetchone()
        if not admin_exists:
            pw_hash, salt = auth.hash_password(Config.ADMIN_PASS)
            conn.execute(
                "INSERT INTO admin_users (username, password_hash, salt, created_at) VALUES (?,?,?,?)", 
                (Config.ADMIN_USER, pw_hash, salt, int(time.time()))
            )
            conn.commit()
        conn.close()
            
    server_address = ('', Config.PORT)
    server = ThreadingHTTPServer(server_address, AmbiRequestHandler)
    logger.info(f"💎 3D Ambi Engine ready at http://localhost:{Config.PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Server shutting down...")

if __name__ == "__main__":
    main()
