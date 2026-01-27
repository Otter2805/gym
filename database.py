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
        cursor = conn.cursor()
        # Sessions: Now with optional metadata columns
        cursor.execute('''CREATE TABLE IF NOT EXISTS sessions 
            (id INTEGER PRIMARY KEY, 
             start_time TEXT, 
             end_time TEXT, 
             status TEXT,
             sleep_score INTEGER,
             fatigue_level INTEGER)''')
        
        # Logs: Individual sets
        cursor.execute('''CREATE TABLE IF NOT EXISTS logs 
            (id INTEGER PRIMARY KEY, 
             session_id INTEGER, 
             exercise TEXT, 
             weight REAL, 
             reps INTEGER, 
             rpe TEXT, 
             timestamp TEXT,
             FOREIGN KEY (session_id) REFERENCES sessions(id))''')
        conn.commit()

# Helper to check for active sessions
def get_active_session():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, start_time FROM sessions WHERE status = 'ACTIVE'")
        return cursor.fetchone()