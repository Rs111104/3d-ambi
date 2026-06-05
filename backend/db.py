import sqlite3
import json
import time
import os

DB_PATH = os.environ.get("DB_PATH", "exam.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as cx:
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
            text TEXT NOT NULL,
            options TEXT NOT NULL -- JSON list
        );
        """)
        
        # Seed questions if empty
        count = cx.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
        if count == 0:
            questions = [
                ("What is the time complexity of quicksort?", json.dumps(["O(n)", "O(n log n)", "O(n²)", "O(log n)"])),
                ("Which data structure uses LIFO?", json.dumps(["Queue", "Stack", "Heap", "Tree"]))
            ]
            cx.executemany("INSERT INTO questions (text, options) VALUES (?,?)", questions)
            cx.commit()

def session_get(sid: str) -> dict | None:
    if not sid: return None
    with get_db() as cx:
        row = cx.execute(
            "SELECT id, current_q, answers, started_at FROM sessions WHERE id=?", (sid,)
        ).fetchone()
    if not row: return None
    return {"id": row[0], "q": row[1],
            "answers": json.loads(row[2]), "started_at": row[3]}

def session_upsert(sid: str, **fields):
    with get_db() as cx:
        # Check if exists
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
