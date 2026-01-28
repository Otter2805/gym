import sqlite3
from datetime import datetime

DB_PATH = 'gym_data.db'

def get_connection():
    return sqlite3.connect(DB_PATH)

def get_last_log_timestamp():
    with get_connection() as conn:
        cursor = conn.cursor()
        # Check logs first, if empty, check sessions
        cursor.execute("SELECT timestamp FROM logs ORDER BY id DESC LIMIT 1")
        res = cursor.fetchone()
        if res: return res[0]
        
        cursor.execute("SELECT start_time FROM sessions ORDER BY id DESC LIMIT 1")
        res = cursor.fetchone()
        return res[0] if res else None

def init_db():
    with get_connection() as conn:
        # 1. Training Splits (The Plan)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_splits (
                user_id INTEGER,
                split_name TEXT, -- 'push', 'pull', 'legs'
                exercise_name TEXT,
                order_index INTEGER, -- To keep exercises in order
                PRIMARY KEY (user_id, split_name, exercise_name)
            )
        """)
        
        # 2. Sessions (The Workout)
        # Part of database.py init_db
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                start_time TEXT,
                end_time TEXT,
                split_name TEXT,
                status TEXT,
                sleep_score INTEGER,
                fatigue_level INTEGER
           )
        """)

        # 3. Logs (The Lifts)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER,
                user_id INTEGER,
                exercise TEXT,
                weight REAL,
                reps INTEGER,
                rpe INTEGER,
                timestamp TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions (id)
            )
        """)

# Helper to check for active sessions
def get_active_session(user_id):
    with get_connection() as conn:
        cursor = conn.cursor()
        # Find the active session belonging specifically to this user
        cursor.execute("""
            SELECT id, split_name FROM sessions 
            WHERE user_id = ? AND status = 'ACTIVE'
        """, (user_id,))
        return cursor.fetchone()