import sqlite3
import threading
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "data.db")
DB_LOCK = threading.RLock()

def db_connect():
    """Returns a connection to the SQLite database with row factory enabled."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes the database schema if it doesn't already exist."""
    with DB_LOCK:
        conn = db_connect()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS questions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    subject TEXT,
                    difficulty TEXT,
                    question_text TEXT,
                    options_json TEXT,
                    correct_index INTEGER,
                    decoy_left_text TEXT,
                    decoy_right_text TEXT,
                    created_at INTEGER
                );
                CREATE TABLE IF NOT EXISTS session_meta (
                    token TEXT PRIMARY KEY,
                    name TEXT,
                    started_at INTEGER,
                    completed_at INTEGER
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    token TEXT PRIMARY KEY,
                    session_key TEXT,
                    next_index INTEGER DEFAULT 0,
                    question_order_json TEXT,
                    answer_received INTEGER DEFAULT 0,
                    integrity_score INTEGER DEFAULT 100,
                    created_at INTEGER
                );
                CREATE TABLE IF NOT EXISTS session_answers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    token TEXT,
                    question_id INTEGER,
                    answer_index INTEGER,
                    correct INTEGER,
                    time_ms INTEGER,
                    head_compliance REAL,
                    created_at INTEGER
                );
                CREATE TABLE IF NOT EXISTS session_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    token TEXT,
                    event_type TEXT,
                    detail TEXT,
                    created_at INTEGER
                );
                CREATE TABLE IF NOT EXISTS admin_users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE,
                    password_hash TEXT,
                    salt TEXT,
                    created_at INTEGER
                );
                CREATE TABLE IF NOT EXISTS admin_sessions (
                    token TEXT PRIMARY KEY,
                    username TEXT,
                    expires_at REAL,
                    csrf_token TEXT
                );
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                );
            """)
            conn.commit()
        finally:
            conn.close()

def get_setting(key: str, default: str = None) -> str:
    """Fetch a configuration value from the persistent settings table."""
    with DB_LOCK:
        conn = db_connect()
        try:
            row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
            return row["value"] if row else default
        finally:
            conn.close()
