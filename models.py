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
    return conn.execute("SELECT * FROM splits ORDER BY sort_order, id").fetchall()


def get_split(conn, split_id):
    return conn.execute("SELECT * FROM splits WHERE id = ?", (split_id,)).fetchone()


def create_split(conn, name):
    """Add a custom split. Returns its id (existing id if the name is taken)."""
    name = name.strip()
    existing = conn.execute("SELECT id FROM splits WHERE name = ?", (name,)).fetchone()
    if existing:
        return existing["id"]
    next_order = conn.execute(
        "SELECT COALESCE(MAX(sort_order), 0) + 1 AS n FROM splits"
    ).fetchone()["n"]
    cur = conn.execute(
        "INSERT INTO splits (name, sort_order, is_custom) VALUES (?, ?, 1)",
        (name, next_order),
    )
    conn.commit()
    return cur.lastrowid


# ---- exercises ----

def get_exercises_for_split(conn, split_id):
    return conn.execute(
        "SELECT * FROM exercises WHERE split_id = ? ORDER BY sort_order, id",
        (split_id,),
    ).fetchall()


def get_exercise(conn, exercise_id):
    return conn.execute("SELECT * FROM exercises WHERE id = ?", (exercise_id,)).fetchone()


def get_all_exercises(conn):
    return conn.execute(
        """
        SELECT exercises.*, splits.name AS split_name
        FROM exercises
        JOIN splits ON splits.id = exercises.split_id
        ORDER BY splits.sort_order, exercises.sort_order, exercises.id
        """
    ).fetchall()


def create_exercise(conn, split_id, muscle_group, name, target_sets,
                    target_rep_range, step_kg, uses_weight):
    """Add a custom exercise to a split. Returns its id (existing id if duplicate name)."""
    name = name.strip()
    existing = conn.execute(
        "SELECT id FROM exercises WHERE split_id = ? AND name = ?", (split_id, name)
    ).fetchone()
    if existing:
        return existing["id"]
    next_order = conn.execute(
        "SELECT COALESCE(MAX(sort_order), 0) + 1 AS n FROM exercises WHERE split_id = ?",
        (split_id,),
    ).fetchone()["n"]
    cur = conn.execute(
        """
        INSERT INTO exercises
            (split_id, muscle_group, name, target_sets, target_rep_range,
             step_kg, sort_order, uses_weight, is_custom)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
        """,
        (split_id, muscle_group.strip() or "Other", name, target_sets,
         target_rep_range, step_kg, next_order, 1 if uses_weight else 0),
    )
    conn.commit()
    return cur.lastrowid


# ---- per-user stats (shared exercise catalogue, separate histories) ----

def get_last_set_for_exercise(conn, user_id, exercise_id, before_session_id=None):
    """Most recent prior set for this user+exercise.

    'Most recent' = latest session date, then latest set. Pass before_session_id to
    exclude the session currently being logged, so "Previous" means last workout.
    """
    query = """
        SELECT sets.*, sessions.date
        FROM sets
        JOIN sessions ON sessions.id = sets.session_id
        WHERE sessions.user_id = ? AND sets.exercise_id = ?
    """
    params = [user_id, exercise_id]
    if before_session_id is not None:
        query += " AND sets.session_id != ?"
        params.append(before_session_id)
    query += " ORDER BY sessions.date DESC, sets.id DESC LIMIT 1"
    return conn.execute(query, params).fetchone()


def get_pb_for_exercise(conn, user_id, exercise_id):
    """Personal best for this user+exercise: heaviest set, ties broken by most reps.

    For bodyweight exercises (no weight recorded) this falls back to the most reps.
    """
    return conn.execute(
        """
        SELECT sets.*, sessions.date
        FROM sets
        JOIN sessions ON sessions.id = sets.session_id
        WHERE sessions.user_id = ? AND sets.exercise_id = ?
        ORDER BY COALESCE(sets.weight_kg, -1) DESC, sets.reps DESC, sets.id DESC
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
    session_id = cur.lastrowid
    # Pre-load the split's exercise pool; the user prunes what they skip.
    for ex in get_exercises_for_split(conn, split_id):
        conn.execute(
            "INSERT OR IGNORE INTO session_exercises (session_id, exercise_id, sort_order) VALUES (?, ?, ?)",
            (session_id, ex["id"], ex["sort_order"]),
        )
    conn.commit()
    return session_id


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
        query += " AND sessions.id IN (SELECT session_id FROM sets WHERE exercise_id = ?)"
        params.append(exercise_id)
    query += " ORDER BY sessions.date DESC, sessions.id DESC"
    return conn.execute(query, params).fetchall()


# ---- session exercise list (add / remove) ----

def get_session_exercises(conn, session_id):
    """Exercises on the plan for this session, with how many sets are logged so far."""
    return conn.execute(
        """
        SELECT exercises.*,
               session_exercises.sort_order AS plan_order,
               (SELECT COUNT(*) FROM sets
                 WHERE sets.session_id = session_exercises.session_id
                   AND sets.exercise_id = exercises.id) AS set_count
        FROM session_exercises
        JOIN exercises ON exercises.id = session_exercises.exercise_id
        WHERE session_exercises.session_id = ?
        ORDER BY session_exercises.sort_order, exercises.id
        """,
        (session_id,),
    ).fetchall()


def add_exercise_to_session(conn, session_id, exercise_id):
    next_order = conn.execute(
        "SELECT COALESCE(MAX(sort_order), 0) + 1 AS n FROM session_exercises WHERE session_id = ?",
        (session_id,),
    ).fetchone()["n"]
    conn.execute(
        "INSERT OR IGNORE INTO session_exercises (session_id, exercise_id, sort_order) VALUES (?, ?, ?)",
        (session_id, exercise_id, next_order),
    )
    conn.commit()


def remove_exercise_from_session(conn, session_id, exercise_id):
    """Drop an exercise from the plan. Logged sets for it are deleted too."""
    conn.execute(
        "DELETE FROM sets WHERE session_id = ? AND exercise_id = ?",
        (session_id, exercise_id),
    )
    conn.execute(
        "DELETE FROM session_exercises WHERE session_id = ? AND exercise_id = ?",
        (session_id, exercise_id),
    )
    conn.commit()


def get_addable_exercises(conn, session_id, split_id):
    """Exercises not already on this session's plan, split into recommended vs the rest.

    Recommended = belongs to the session's split. The rest is everything else,
    which is what the "..." list shows.
    """
    on_plan = {
        r["exercise_id"]
        for r in conn.execute(
            "SELECT exercise_id FROM session_exercises WHERE session_id = ?", (session_id,)
        ).fetchall()
    }
    recommended, others = [], []
    for ex in get_all_exercises(conn):
        if ex["id"] in on_plan:
            continue
        (recommended if ex["split_id"] == split_id else others).append(ex)
    return recommended, others


# ---- sets ----

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


def get_sets_for_exercise_in_session(conn, session_id, exercise_id):
    return conn.execute(
        """
        SELECT * FROM sets
        WHERE session_id = ? AND exercise_id = ?
        ORDER BY set_number
        """,
        (session_id, exercise_id),
    ).fetchall()


def log_set(conn, session_id, exercise_id, weight_kg, reps):
    next_number = conn.execute(
        "SELECT COALESCE(MAX(set_number), 0) + 1 AS n FROM sets WHERE session_id = ? AND exercise_id = ?",
        (session_id, exercise_id),
    ).fetchone()["n"]
    cur = conn.execute(
        "INSERT INTO sets (session_id, exercise_id, set_number, weight_kg, reps) VALUES (?, ?, ?, ?, ?)",
        (session_id, exercise_id, next_number, weight_kg, reps),
    )
    conn.commit()
    return cur.lastrowid, next_number


def delete_set(conn, set_id, session_id):
    """Remove one logged set, then renumber what's left so set_number stays 1..n."""
    row = conn.execute(
        "SELECT exercise_id FROM sets WHERE id = ? AND session_id = ?", (set_id, session_id)
    ).fetchone()
    if not row:
        return False
    conn.execute("DELETE FROM sets WHERE id = ?", (set_id,))
    remaining = conn.execute(
        "SELECT id FROM sets WHERE session_id = ? AND exercise_id = ? ORDER BY set_number, id",
        (session_id, row["exercise_id"]),
    ).fetchall()
    for i, r in enumerate(remaining, start=1):
        conn.execute("UPDATE sets SET set_number = ? WHERE id = ?", (i, r["id"]))
    conn.commit()
    return True


def get_set_count_for_exercise(conn, session_id, exercise_id):
    return conn.execute(
        "SELECT COUNT(*) AS n FROM sets WHERE session_id = ? AND exercise_id = ?",
        (session_id, exercise_id),
    ).fetchone()["n"]


# ---- progress ----

def get_all_exercise_names(conn, user_id):
    """Distinct exercises this user has ever logged a set for (for the dropdowns)."""
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

def update_session(conn, session_id, date, notes):
    conn.execute(
        "UPDATE sessions SET date = ?, notes = ? WHERE id = ?",
        (date, notes, session_id),
    )
    conn.commit()


def delete_session(conn, session_id):
    """Delete a whole session and everything hanging off it."""
    conn.execute("DELETE FROM sets WHERE session_id = ?", (session_id,))
    conn.execute("DELETE FROM session_exercises WHERE session_id = ?", (session_id,))
    conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    conn.commit()


def update_set(conn, set_id, session_id, weight_kg, reps):
    """Correct a logged set. session_id is passed so a set can only be edited
    through the session that owns it."""
    conn.execute(
        "UPDATE sets SET weight_kg = ?, reps = ? WHERE id = ? AND session_id = ?",
        (weight_kg, reps, set_id, session_id),
    )
    conn.commit()


def get_export_rows(conn, user_id, split_id=None, exercise_id=None):
    """Flat one-row-per-set view for CSV export, honouring the history filters."""
    query = """
        SELECT sessions.date, splits.name AS split, exercises.muscle_group,
               exercises.name AS exercise, sets.set_number, sets.weight_kg,
               sets.reps, sessions.notes, users.name AS user
        FROM sets
        JOIN sessions ON sessions.id = sets.session_id
        JOIN splits ON splits.id = sessions.split_id
        JOIN exercises ON exercises.id = sets.exercise_id
        JOIN users ON users.id = sessions.user_id
        WHERE sessions.user_id = ?
    """
    params = [user_id]
    if split_id:
        query += " AND sessions.split_id = ?"
        params.append(split_id)
    if exercise_id:
        query += " AND sets.exercise_id = ?"
        params.append(exercise_id)
    query += " ORDER BY sessions.date DESC, sessions.id DESC, exercises.name, sets.set_number"
    return conn.execute(query, params).fetchall()
