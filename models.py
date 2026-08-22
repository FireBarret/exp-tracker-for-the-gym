"""SQLite access helpers. Plain sqlite3, no ORM -- this app is small enough not to need one."""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "gym.db"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_schema(db_path=DB_PATH):
    schema_path = Path(__file__).parent / "schema.sql"
    conn = sqlite3.connect(db_path)
    with open(schema_path) as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()


# ---- users / splits ----

def get_users(conn):
    return conn.execute("SELECT * FROM users ORDER BY id").fetchall()


def get_user(conn, user_id):
    return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def get_splits(conn):
    return conn.execute("SELECT * FROM splits ORDER BY id").fetchall()


def get_split(conn, split_id):
    return conn.execute("SELECT * FROM splits WHERE id = ?", (split_id,)).fetchone()


# ---- exercises ----

def get_exercises_for_split(conn, split_id):
    return conn.execute(
        "SELECT * FROM exercises WHERE split_id = ? ORDER BY sort_order, id",
        (split_id,),
    ).fetchall()


def get_exercise(conn, exercise_id):
    return conn.execute("SELECT * FROM exercises WHERE id = ?", (exercise_id,)).fetchone()


def get_last_set_for_exercise(conn, user_id, exercise_id):
    """Most recent prior set for this user+exercise, across all past sessions.

    'Most recent' = latest session date, then latest set within that session.
    """
    return conn.execute(
        """
        SELECT sets.*
        FROM sets
        JOIN sessions ON sessions.id = sets.session_id
        WHERE sessions.user_id = ? AND sets.exercise_id = ?
        ORDER BY sessions.date DESC, sets.id DESC
        LIMIT 1
        """,
        (user_id, exercise_id),
    ).fetchone()


# ---- sessions ----

def create_session(conn, user_id, split_id, date):
    cur = conn.execute(
        "INSERT INTO sessions (user_id, split_id, date) VALUES (?, ?, ?)",
        (user_id, split_id, date),
    )
    conn.commit()
    return cur.lastrowid


def get_session(conn, session_id):
    return conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()


def update_session_notes(conn, session_id, notes):
    conn.execute("UPDATE sessions SET notes = ? WHERE id = ?", (notes, session_id))
    conn.commit()


def get_sessions_for_user(conn, user_id, split_id=None, exercise_id=None):
    query = """
        SELECT sessions.*, splits.name AS split_name
        FROM sessions
        JOIN splits ON splits.id = sessions.split_id
        WHERE sessions.user_id = ?
    """
    params = [user_id]
    if split_id:
        query += " AND sessions.split_id = ?"
        params.append(split_id)
    if exercise_id:
        query += """
            AND sessions.id IN (
                SELECT session_id FROM sets WHERE exercise_id = ?
            )
        """
        params.append(exercise_id)
    query += " ORDER BY sessions.date DESC, sessions.id DESC"
    return conn.execute(query, params).fetchall()


def get_sets_for_session(conn, session_id):
    return conn.execute(
        """
        SELECT sets.*, exercises.name AS exercise_name, exercises.muscle_group
        FROM sets
        JOIN exercises ON exercises.id = sets.exercise_id
        WHERE sets.session_id = ?
        ORDER BY exercises.sort_order, sets.exercise_id, sets.set_number
        """,
        (session_id,),
    ).fetchall()


# ---- sets ----

def get_next_set_number(conn, session_id, exercise_id):
    row = conn.execute(
        "SELECT COALESCE(MAX(set_number), 0) AS n FROM sets WHERE session_id = ? AND exercise_id = ?",
        (session_id, exercise_id),
    ).fetchone()
    return row["n"] + 1


def log_set(conn, session_id, exercise_id, weight_kg, reps):
    set_number = get_next_set_number(conn, session_id, exercise_id)
    cur = conn.execute(
        "INSERT INTO sets (session_id, exercise_id, set_number, weight_kg, reps) VALUES (?, ?, ?, ?, ?)",
        (session_id, exercise_id, set_number, weight_kg, reps),
    )
    conn.commit()
    return cur.lastrowid, set_number


def get_set_count_for_exercise(conn, session_id, exercise_id):
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM sets WHERE session_id = ? AND exercise_id = ?",
        (session_id, exercise_id),
    ).fetchone()
    return row["n"]


# ---- progress ----

def get_all_exercise_names(conn, user_id):
    """Distinct exercises this user has ever logged a set for (for the progress dropdown)."""
    return conn.execute(
        """
        SELECT DISTINCT exercises.id, exercises.name
        FROM exercises
        JOIN sets ON sets.exercise_id = exercises.id
        JOIN sessions ON sessions.id = sets.session_id
        WHERE sessions.user_id = ?
        ORDER BY exercises.name
        """,
        (user_id,),
    ).fetchall()


def get_progress_series(conn, user_id, exercise_id):
    """Top set (max weight_kg) per session, in date order, for this user+exercise."""
    return conn.execute(
        """
        SELECT sessions.date, MAX(sets.weight_kg) AS top_weight_kg
        FROM sets
        JOIN sessions ON sessions.id = sets.session_id
        WHERE sessions.user_id = ? AND sets.exercise_id = ?
        GROUP BY sessions.id
        ORDER BY sessions.date ASC, sessions.id ASC
        """,
        (user_id, exercise_id),
    ).fetchall()
