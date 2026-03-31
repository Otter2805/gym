import sqlite3
import os

# use an absolute path so the DB file is always in the same place regardless of where you start the bot from
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'gym_database', 'gym_data.db')

def get_connection():
    """
    Creates a connection and forces SQLite to write to the main file 
    immediately rather than using a sidecar -wal file.
    """
    conn = sqlite3.connect(DB_PATH)
    # ournal_mode=DELETE ensures data goes straight to gym_data.db
    conn.execute("PRAGMA journal_mode=DELETE;")
    conn.execute("PRAGMA synchronous=FULL;")
    return conn

def init_db():
    conn = get_connection()
    try:
        with conn:
            # 1. Training Splits
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_splits (
                    user_id INTEGER,
                    split_name TEXT,
                    exercise_name TEXT,
                    order_index INTEGER,
                    PRIMARY KEY (user_id, split_name, exercise_name)
                )
            """)
            
            # 2. Workout Sessions
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

            # 3. Lift Logs
            conn.execute("""
                CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER,
                    user_id INTEGER,
                    exercise TEXT,
                    weight REAL,
                    reps INTEGER,
                    rpe TEXT,
                    timestamp TEXT,
                    FOREIGN KEY (session_id) REFERENCES sessions (id)
                )
            """)

            # 4. Master Exercise List
            conn.execute("""
                CREATE TABLE IF NOT EXISTS exercises (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE,
                    category TEXT
                )
            """)

            # 5. Shorthand Aliases
            conn.execute("""
                CREATE TABLE IF NOT EXISTS exercise_aliases (
                    alias TEXT PRIMARY KEY,
                    exercise_id INTEGER,
                    FOREIGN KEY (exercise_id) REFERENCES exercises (id)
                )
            """)
        seed_exercises()
    finally:
        conn.close()

def seed_exercises():
    exercises = [
        ('bench_press', 'Chest'), ('incline_db_press', 'Chest'), ('chest_fly', 'Chest'),
        ('dip', 'Chest'), ('incline_smith_bench', 'Chest'), ('deadlift', 'Back'),
        ('pull_up', 'Back'), ('lat_pulldown', 'Back'), ('bent_over_barbell_row', 'Back'),
        ('seated_cable_row', 'Back'), ('chest_supported_row', 'Back'), ('iso_lat_pulldown', 'Back'),
        ('squat', 'Legs'), ('leg_press', 'Legs'), ('leg_extension', 'Legs'),
        ('leg_curl', 'Legs'), ('romanian_deadlift', 'Legs'), ('calf_raise', 'Legs'),
        ('barbell_overhead_press', 'Shoulders'), ('db_overhead_press', 'Shoulders'),
        ('db_lat_raise', 'Shoulders'), ('cable_lat_raise', 'Shoulders'), ('face_pull', 'Shoulders'),
        ('rear_delt_flys', 'Shoulders'), ('bicep_curl', 'Bicep'), ('preacher_curl', 'Bicep'),
        ('incline_curl', 'Bicep'), ('barbell_curl', 'Bicep'), ('tricep_pushdown', 'Tricep'),
        ('skullcrusher', 'Tricep'), ('close_grip_bench_press', 'Tricep'), ('hammer_curl', 'Bicep'),
        ('plank', 'Core'), ('hanging_leg_raise', 'Core')
    ]
    
    conn = get_connection()
    try:
        with conn:
            conn.executemany(
                "INSERT OR IGNORE INTO exercises (name, category) VALUES (?, ?)", 
                exercises
            )
    finally:
        conn.close()

def get_active_session(user_id):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, split_name FROM sessions 
            WHERE user_id = ? AND status = 'ACTIVE'
        """, (user_id,))
        return cursor.fetchone()
    finally:
        conn.close()

def resolve_exercise(input_name):
    name = input_name.lower().strip()
    conn = get_connection()
    try:
        # Check master list
        res = conn.execute("SELECT name FROM exercises WHERE name = ?", (name,)).fetchone()
        if res:
            return res[0]

        # Check aliases
        res = conn.execute("""
            SELECT e.name FROM exercises e
            JOIN exercise_aliases a ON e.id = a.exercise_id
            WHERE a.alias = ?
        """, (name,)).fetchone()
        
        return res[0] if res else None
    finally:
        conn.close()

def get_last_log_timestamp():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT timestamp FROM logs ORDER BY id DESC LIMIT 1")
        res = cursor.fetchone()
        if res: return res[0]
        
        cursor.execute("SELECT start_time FROM sessions ORDER BY id DESC LIMIT 1")
        res = cursor.fetchone()
        return res[0] if res else None
    finally:
        conn.close()