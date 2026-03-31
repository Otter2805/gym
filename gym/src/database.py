import sqlite3
from datetime import datetime
import os

DB_PATH = os.getenv('DATABASE_URL', 'gym_data.db')

def seed_exercises():
    exercises = [
        # Chest
        ('bench_press', 'Chest'),
        ('incline_db_press', 'Chest'),
        ('chest_fly', 'Chest'),
        ('dip', 'Chest'),
        ('incline_smith_bench', 'Chest'),
        ('dip', 'Chest'),
        # Back
        ('deadlift', 'Back'),
        ('pull_up', 'Back'),
        ('lat_pulldown', 'Back'),
        ('bent_over_barbell_row', 'Back'),
        ('seated_cable_row', 'Back'),
        ('chest_supported_row', 'Back'),
        ('iso_lat_pulldown', 'Back'),
        # Legs
        ('squat', 'Legs'),
        ('leg_press', 'Legs'),
        ('leg_extension', 'Legs'),
        ('leg_curl', 'Legs'),
        ('romanian_deadlift', 'Legs'),
        ('calf_raise', 'Legs'),
        # Shoulders
        ('barbell_overhead_press', 'Shoulders'),
        ('db_overhead_press', 'Shoulders'),
        ('db_lat_raise', 'Shoulders'),
        ('cable_lat_raise', 'Shoulders'),
        ('face_pull', 'Shoulders'),
        ('rear_delt_flys', 'Shoulders'),
        # Arms
        ('bicep_curl', 'Bicep'),
        ('preacher_curl', 'Bicep'),
        ('incline_curl', 'Bicep'),
        ('barbell_curl', 'Bicep'),
        ('tricep_pushdown', 'Tricep'),
        ('skullcrusher', 'Tricep'),
        ('close_grip_bench_press', 'Tricep'),
        ('hammer_curl', 'Bicep'),
        # Core
        ('plank', 'Core'),
        ('hanging_leg_raise', 'Core')
    ]
    
    with get_connection() as conn:
        conn.executemany(
            "INSERT OR IGNORE INTO exercises (name, category) VALUES (?, ?)", 
            exercises
        )
    print(f"Seeded {len(exercises)} master exercises.")

def get_connection():
    db_dir = os.path.dirname(DB_PATH)

    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
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
                split_name TEXT,
                exercise_name TEXT,
                order_index INTEGER,
                PRIMARY KEY (user_id, split_name, exercise_name)
            )
        """)
        
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

        conn.execute("""
            CREATE TABLE IF NOT EXISTS exercises (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE, -- e.g., 'bench_press'
                category TEXT     -- e.g., 'Chest'
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS exercise_aliases (
                alias TEXT PRIMARY KEY, -- e.g., 'bp', 'bench'
                exercise_id INTEGER,
                FOREIGN KEY (exercise_id) REFERENCES exercises (id)
            )
        """)
        seed_exercises()

def get_active_session(user_id):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, split_name FROM sessions 
            WHERE user_id = ? AND status = 'ACTIVE'
        """, (user_id,))
        return cursor.fetchone()
    
def resolve_exercise(input_name):
    name = input_name.lower().strip()
    with get_connection() as conn:
        res = conn.execute("SELECT name FROM exercises WHERE name = ?", (name,)).fetchone()
        if res:
            return res[0]

        res = conn.execute("""
            SELECT e.name FROM exercises e
            JOIN exercise_aliases a ON e.id = a.exercise_id
            WHERE a.alias = ?
        """, (name,)).fetchone()
        
        return res[0] if res else None