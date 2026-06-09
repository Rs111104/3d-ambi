import sqlite3
import json
import time
import os
from contextlib import contextmanager

DB_PATH = os.environ.get("DB_PATH", "exam.db")

_wal_initialized = False

@contextmanager
def get_db():
    """Context manager that properly closes the connection after use.
    
    The default sqlite3 `with conn` only manages transactions (commit/rollback),
    it does NOT close the connection, causing file handle leaks.
    """
    global _wal_initialized
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    conn.row_factory = sqlite3.Row
    if not _wal_initialized:
        conn.execute("PRAGMA journal_mode=WAL")
        _wal_initialized = True
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    with get_db() as cx:
        # Check if questions table lacks the subject or correct_index columns
        try:
            cx.execute("SELECT subject, correct_index FROM questions LIMIT 1")
        except sqlite3.OperationalError:
            cx.execute("DROP TABLE IF EXISTS questions")

        cx.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            exam_id TEXT,
            candidate_email TEXT,
            current_q INTEGER DEFAULT 0,
            answers TEXT DEFAULT '{}',
            consented_at REAL,
            started_at REAL,
            finished_at REAL,
            integrity_score INTEGER DEFAULT 100
        );
        CREATE TABLE IF NOT EXISTS flag_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL REFERENCES sessions(id),
            event_type TEXT NOT NULL,
            ts REAL NOT NULL,
            duration_ms INTEGER,
            detail TEXT
        );
        CREATE TABLE IF NOT EXISTS admin_sessions (
            token TEXT PRIMARY KEY,
            created_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT DEFAULT 'General',
            text TEXT NOT NULL,
            options TEXT NOT NULL, -- JSON list
            correct_index INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        """)
        
        # Seed questions if empty
        count = cx.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
        if count == 0:
            questions = [
                ("CS", "What is the time complexity of quicksort?", json.dumps(["O(n)", "O(n log n)", "O(n²)", "O(log n)"]), 1),
                ("CS", "Which data structure uses LIFO?", json.dumps(["Queue", "Stack", "Heap", "Tree"]), 1),
                ("Science", "What is H2O?", json.dumps(["Water", "Acid", "Salt", "Gas"]), 0),
                ("History", "Who wrote the Great Gatsby?", json.dumps(["F. Scott Fitzgerald", "Ernest Hemingway", "Mark Twain", "Charles Dickens"]), 0),
                ("Tech", "Which architectural pattern decouples storage from logic?", json.dumps(["MVC", "Monolith", "Serverless", "Edge"]), 0)
            ]
            cx.executemany("INSERT INTO questions (subject, text, options, correct_index) VALUES (?,?,?,?)", questions)
            
        # Seed default settings if empty
        settings_count = cx.execute("SELECT COUNT(*) FROM settings").fetchone()[0]
        if settings_count == 0:
            cx.execute("INSERT INTO settings (key, value) VALUES (?,?)", ("inactivity_timeout", "300"))
            cx.execute("INSERT INTO settings (key, value) VALUES (?,?)", ("integrity_threshold", "80"))
        
        # H4: Purge expired admin sessions (older than 1 hour)
        cx.execute("DELETE FROM admin_sessions WHERE created_at < ?", (time.time() - 3600,))
        
        cx.commit()

def session_get(sid: str) -> dict | None:
    if not sid: return None
    with get_db() as cx:
        row = cx.execute(
            "SELECT id, current_q, answers, started_at, finished_at FROM sessions WHERE id=?", (sid,)
        ).fetchone()
        if not row: return None
        return {"id": row[0], "q": row[1],
                "answers": json.loads(row[2]), "started_at": row[3], "finished_at": row[4]}

# C2: Whitelist of valid session columns to prevent SQL injection via key names
_SESSION_COLUMNS = frozenset({
    "exam_id", "candidate_email", "current_q", "answers",
    "consented_at", "started_at", "finished_at", "integrity_score"
})

def session_upsert(sid: str, **fields):
    # Reject any keys not in the whitelist
    invalid = set(fields.keys()) - _SESSION_COLUMNS
    if invalid:
        raise ValueError(f"Invalid session fields: {invalid}")
    
    with get_db() as cx:
        exists = cx.execute("SELECT 1 FROM sessions WHERE id=?", (sid,)).fetchone()
        if exists:
            set_clause = ", ".join([f"{k}=?" for k in fields.keys()])
            vals = list(fields.values()) + [sid]
            cx.execute(f"UPDATE sessions SET {set_clause} WHERE id=?", vals)
        else:
            cols = ", ".join(["id"] + list(fields.keys()))
            placeholders = ", ".join(["?"] * (len(fields) + 1))
            vals = [sid] + list(fields.values())
            cx.execute(f"INSERT INTO sessions ({cols}) VALUES ({placeholders})", vals)
        cx.commit()

def log_flag(sid: str, event_type: str, detail: str = None, duration_ms: int = None):
    with get_db() as cx:
        cx.execute(
            "INSERT INTO flag_events (session_id, event_type, ts, duration_ms, detail) VALUES (?,?,?,?,?)",
            (sid, event_type, time.time(), duration_ms, detail)
        )
        cx.commit()
