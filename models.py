"""SQLite access helpers. Plain sqlite3, no ORM -- this app is small enough not to need one."""
import sqlite3
from translations import muscle_group as muscle_group_name
from datetime import date, datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent / "gym.db"


def get_db(env=None):
    """`env` is the Worker's bindings object (request.environ["workers.env"]).
    Passed -> D1 (production, Cloudflare Workers). Omitted -> local sqlite3
    file, for `flask run` / the management scripts (init_db.py, migrate.py,
    seed.py) that still talk to a real gym.db on disk."""
    if env is not None:
        from d1_compat import D1Connection
        return D1Connection(env.DB)
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


def create_split(conn, name, name_ja=None):
    """Add a custom split. Returns its id (existing id if the name is taken)."""
    name = name.strip()
    existing = conn.execute("SELECT id FROM splits WHERE name = ?", (name,)).fetchone()
    if existing:
        return existing["id"]
    next_order = conn.execute(
        "SELECT COALESCE(MAX(sort_order), 0) + 1 AS n FROM splits"
    ).fetchone()["n"]
    cur = conn.execute(
        "INSERT INTO splits (name, name_ja, sort_order, is_custom) VALUES (?, ?, ?, 1)",
        (name, (name_ja or "").strip() or None, next_order),
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
                    target_rep_range, step_kg, uses_weight=None,
                    name_ja=None, weight_mode="added"):
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
    if uses_weight is None:
        uses_weight = weight_mode != "none"
    cur = conn.execute(
        """
        INSERT INTO exercises
            (split_id, muscle_group, name, name_ja, target_sets, target_rep_range,
             step_kg, sort_order, uses_weight, weight_mode, is_custom)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        """,
        (split_id, muscle_group.strip() or "Other", name, (name_ja or "").strip() or None,
         target_sets, target_rep_range, step_kg, next_order,
         1 if uses_weight else 0, weight_mode),
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
    """Personal best for this user+exercise.

    Normally the heaviest set wins, ties broken by reps. On an assistance machine
    the scale runs the other way -- less assistance is a stronger effort -- so the
    lightest set wins instead. Bodyweight exercises fall back to the most reps.
    """
    exercise = get_exercise(conn, exercise_id)
    assisted = exercise is not None and exercise["weight_mode"] == "assisted"
    order = ("COALESCE(sets.weight_kg, 1e9) ASC" if assisted
             else "COALESCE(sets.weight_kg, -1) DESC")
    return conn.execute(
        f"""
        SELECT sets.*, sessions.date
        FROM sets
        JOIN sessions ON sessions.id = sets.session_id
        WHERE sessions.user_id = ? AND sets.exercise_id = ?
        ORDER BY {order}, sets.reps DESC, sets.id DESC
        LIMIT 1
        """,
        (user_id, exercise_id),
    ).fetchone()


# ---- sessions ----

def create_session(conn, user_id, split_id, date):
    # Only one workout can be in progress at a time -- close whatever was left open.
    active = get_active_session(conn, user_id)
    if active:
        finish_session(conn, active["id"])
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
        SELECT sessions.*, splits.name AS split_name, splits.name_ja AS split_name_ja
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
        SELECT sets.*, exercises.name AS exercise_name,
               exercises.name_ja AS exercise_name_ja, exercises.muscle_group
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
        SELECT DISTINCT exercises.id, exercises.name, exercises.name_ja
        FROM exercises
        JOIN sets ON sets.exercise_id = exercises.id
        JOIN sessions ON sessions.id = sets.session_id
        WHERE sessions.user_id = ?
        ORDER BY exercises.name
        """,
        (user_id,),
    ).fetchall()


def get_progress_series(conn, user_id, exercise_id):
    """Best set per session, in date order. 'Best' is the heaviest normally and
    the lightest on an assistance machine."""
    exercise = get_exercise(conn, exercise_id)
    assisted = exercise is not None and exercise["weight_mode"] == "assisted"
    agg = "MIN" if assisted else "MAX"
    return conn.execute(
        f"""
        SELECT sessions.date, {agg}(sets.weight_kg) AS top_weight_kg
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

# ---- resuming an in-progress workout ----

def get_active_session(conn, user_id, within_days=1):
    """The workout this user still has open, if any.

    A session counts as in progress until it's explicitly finished. Anything
    older than `within_days` is ignored so a workout abandoned last week doesn't
    keep offering itself -- the window is a day rather than "today" so a session
    started before midnight can still be resumed after it.
    """
    cutoff = (date.today() - timedelta(days=within_days)).isoformat()
    return conn.execute(
        """
        SELECT sessions.*, splits.name AS split_name, splits.name_ja AS split_name_ja,
               (SELECT COUNT(*) FROM sets WHERE sets.session_id = sessions.id) AS set_count
        FROM sessions
        JOIN splits ON splits.id = sessions.split_id
        WHERE sessions.user_id = ?
          AND sessions.finished_at IS NULL
          AND sessions.date >= ?
        ORDER BY sessions.id DESC
        LIMIT 1
        """,
        (user_id, cutoff),
    ).fetchone()


def finish_session(conn, session_id):
    """Close a workout. An empty one is deleted rather than kept -- a session with
    no sets is just noise in history. Returns True if it was deleted."""
    count = conn.execute(
        "SELECT COUNT(*) AS n FROM sets WHERE session_id = ?", (session_id,)
    ).fetchone()["n"]
    if count == 0:
        delete_session(conn, session_id)
        return True
    conn.execute(
        "UPDATE sessions SET finished_at = ? WHERE id = ?",
        (datetime.now().isoformat(timespec="seconds"), session_id),
    )
    conn.commit()
    return False


def reopen_session(conn, session_id):
    """Mark a finished session as in progress again (used by Resume on history)."""
    conn.execute("UPDATE sessions SET finished_at = NULL WHERE id = ?", (session_id,))
    conn.commit()

def get_session_exercise_data(conn, user_id, session_id, lang="en"):
    """Everything the log screen needs for every exercise on the plan, in two
    queries rather than three per exercise.

    The session page ships this to the browser as JSON so tapping an exercise
    opens its entry screen with no further request -- which matters a lot when
    the server is slow to answer.
    """
    rows = conn.execute(
        """
        SELECT e.id, e.name, e.name_ja, e.muscle_group, e.target_sets,
               e.target_rep_range, e.step_kg, e.uses_weight, e.weight_mode,
               se.sort_order AS plan_order,
               prev.weight_kg AS prev_weight, prev.reps AS prev_reps,
               pb.weight_kg   AS pb_weight,   pb.reps   AS pb_reps
        FROM session_exercises se
        JOIN exercises e ON e.id = se.exercise_id
        LEFT JOIN sets prev ON prev.id = (
            SELECT s.id FROM sets s
            JOIN sessions ss ON ss.id = s.session_id
            WHERE ss.user_id = ? AND s.exercise_id = e.id AND s.session_id != ?
            ORDER BY ss.date DESC, s.id DESC LIMIT 1
        )
        LEFT JOIN sets pb ON pb.id = (
            SELECT s.id FROM sets s
            JOIN sessions ss ON ss.id = s.session_id
            WHERE ss.user_id = ? AND s.exercise_id = e.id
            ORDER BY COALESCE(s.weight_kg, -1) DESC, s.reps DESC, s.id DESC LIMIT 1
        )
        WHERE se.session_id = ?
        ORDER BY se.sort_order, e.id
        """,
        (user_id, session_id, user_id, session_id),
    ).fetchall()

    logged = {}
    for st in conn.execute(
        "SELECT id, exercise_id, set_number, weight_kg, reps FROM sets "
        "WHERE session_id = ? ORDER BY exercise_id, set_number",
        (session_id,),
    ).fetchall():
        logged.setdefault(st["exercise_id"], []).append(
            {"id": st["id"], "n": st["set_number"],
             "weight": st["weight_kg"], "reps": st["reps"]}
        )

    out = []
    for r in rows:
        sets = logged.get(r["id"], [])
        out.append({
            "id": r["id"],
            "name": display_name(r, lang),
            "muscle_group": muscle_group_name(r["muscle_group"], lang),
            "weight_mode": r["weight_mode"],
            "target_sets": r["target_sets"],
            "target_reps": r["target_rep_range"],
            "step": r["step_kg"],
            "uses_weight": bool(r["uses_weight"]),
            "previous": None if r["prev_reps"] is None else
                        {"weight": r["prev_weight"], "reps": r["prev_reps"]},
            "pb": None if r["pb_reps"] is None else
                  {"weight": r["pb_weight"], "reps": r["pb_reps"]},
            "sets": sets,
        })
    return out

# ---- schema self-healing ----
#
# Additive schema changes are applied on startup rather than waiting for someone
# to remember `python migrate.py`. Every statement here is additive (a new column
# or table), so it cannot lose data, and each is guarded by a check plus a
# tolerant except in case two workers start at once.
#
# The one migration NOT done here is the six-splits-to-three rebuild, which
# rewrites rows and takes a backup first -- that stays a deliberate manual step.

_ADDITIVE_COLUMNS = [
    # (table, column, definition, backfill SQL or None)
    ("users", "lang", "TEXT NOT NULL DEFAULT 'en'", None),
    ("splits", "name_ja", "TEXT", None),
    ("exercises", "name_ja", "TEXT", None),
    ("exercises", "weight_mode", "TEXT NOT NULL DEFAULT 'added'",
     "UPDATE exercises SET weight_mode = 'none' WHERE uses_weight = 0"),
    ("sessions", "notes", "TEXT", None),
    ("sessions", "finished_at", "TEXT",
     "UPDATE sessions SET finished_at = date WHERE finished_at IS NULL"),
    ("exercises", "uses_weight", "INTEGER NOT NULL DEFAULT 1", None),
    ("exercises", "is_custom", "INTEGER NOT NULL DEFAULT 0", None),
    ("splits", "sort_order", "INTEGER NOT NULL DEFAULT 0", None),
    ("splits", "is_custom", "INTEGER NOT NULL DEFAULT 0", None),
]


def _table_exists(conn, name):
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def ensure_schema_current(conn):
    """Bring an older database up to date. Idempotent; returns what it changed."""
    applied = []

    for table, column, definition, backfill in _ADDITIVE_COLUMNS:
        if not _table_exists(conn, table):
            continue
        cols = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        if column in cols:
            continue
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
            if backfill:
                conn.execute(backfill)
            conn.commit()
            applied.append(f"{table}.{column}")
        except sqlite3.OperationalError as exc:
            # Another worker got there first -- fine. Anything else is real.
            if "duplicate column" not in str(exc).lower():
                raise

    # Japanese names ship with the app but live in the database, so a deploy has
    # to put them on rows that predate the column -- otherwise the UI translates
    # and every exercise stays stubbornly English.
    if _table_exists(conn, "exercises"):
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(exercises)").fetchall()}
        if "name_ja" in cols and conn.execute(
            "SELECT 1 FROM exercises WHERE name_ja IS NULL OR name_ja = '' LIMIT 1"
        ).fetchone():
            try:
                from seed import backfill_translations
                filled = backfill_translations(conn)
                if filled:
                    applied.append(f"japanese names ({filled})")
            except Exception:
                pass        # a missing seed module must not stop the app booting

    if _table_exists(conn, "sessions") and not _table_exists(conn, "session_exercises"):
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS session_exercises (
              id INTEGER PRIMARY KEY,
              session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
              exercise_id INTEGER NOT NULL REFERENCES exercises(id),
              sort_order INTEGER NOT NULL DEFAULT 0,
              UNIQUE(session_id, exercise_id)
            );
            CREATE INDEX IF NOT EXISTS idx_session_exercises_session
              ON session_exercises(session_id);
            """
        )
        # Give past sessions a plan built from whatever they actually logged.
        conn.execute(
            "INSERT OR IGNORE INTO session_exercises (session_id, exercise_id, sort_order) "
            "SELECT DISTINCT session_id, exercise_id, 0 FROM sets"
        )
        conn.commit()
        applied.append("session_exercises")

    return applied


def needs_full_migration(conn):
    """True when the six-split layout is still in place and migrate.py must run."""
    if not _table_exists(conn, "splits"):
        return False
    names = {r["name"] for r in conn.execute("SELECT name FROM splits").fetchall()}
    return bool(names & {"Push 1", "Push 2", "Pull 1", "Pull 2", "Legs 1", "Legs 2"})

# ---- accounts ----

def get_user_by_name(conn, name):
    """Look up an account by name, ignoring case and surrounding whitespace."""
    return conn.execute(
        "SELECT * FROM users WHERE name = ? COLLATE NOCASE", (name.strip(),)
    ).fetchone()


def create_user(conn, name):
    cur = conn.execute("INSERT INTO users (name) VALUES (?)", (name.strip(),))
    conn.commit()
    return cur.lastrowid


def get_or_create_user(conn, name):
    """Returns (user_row, created). Signing in with an unused name makes an account."""
    existing = get_user_by_name(conn, name)
    if existing:
        return existing, False
    user_id = create_user(conn, name)
    return get_user(conn, user_id), True


def rename_user(conn, user_id, new_name):
    """Returns an error string, or None on success."""
    new_name = new_name.strip()
    if not new_name:
        return "Name can't be empty."
    clash = conn.execute(
        "SELECT id FROM users WHERE name = ? COLLATE NOCASE AND id != ?",
        (new_name, user_id),
    ).fetchone()
    if clash:
        return f"There's already an account called {new_name}."
    conn.execute("UPDATE users SET name = ? WHERE id = ?", (new_name, user_id))
    conn.commit()
    return None


def delete_user(conn, user_id):
    """Remove an account and everything it logged."""
    session_ids = [
        r["id"] for r in
        conn.execute("SELECT id FROM sessions WHERE user_id = ?", (user_id,)).fetchall()
    ]
    for sid in session_ids:
        conn.execute("DELETE FROM sets WHERE session_id = ?", (sid,))
        conn.execute("DELETE FROM session_exercises WHERE session_id = ?", (sid,))
    conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()


def user_stats(conn, user_id):
    return conn.execute(
        """
        SELECT (SELECT COUNT(*) FROM sessions WHERE user_id = ?) AS sessions,
               (SELECT COUNT(*) FROM sets JOIN sessions ON sessions.id = sets.session_id
                 WHERE sessions.user_id = ?) AS sets
        """,
        (user_id, user_id),
    ).fetchone()


# ---- editing splits and exercises ----

def update_split(conn, split_id, name, name_ja=None):
    name = name.strip()
    if not name:
        return "Name can't be empty."
    clash = conn.execute(
        "SELECT id FROM splits WHERE name = ? COLLATE NOCASE AND id != ?", (name, split_id)
    ).fetchone()
    if clash:
        return f"There's already a split called {name}."
    conn.execute("UPDATE splits SET name = ?, name_ja = ? WHERE id = ?",
                 (name, (name_ja or "").strip() or None, split_id))
    conn.commit()
    return None


def split_usage(conn, split_id):
    return conn.execute(
        """
        SELECT (SELECT COUNT(*) FROM exercises WHERE split_id = ?) AS exercises,
               (SELECT COUNT(*) FROM sessions WHERE split_id = ?) AS sessions
        """,
        (split_id, split_id),
    ).fetchone()


def delete_split(conn, split_id):
    """Delete a split, its exercises, and every session logged against it."""
    for r in conn.execute("SELECT id FROM sessions WHERE split_id = ?", (split_id,)).fetchall():
        conn.execute("DELETE FROM sets WHERE session_id = ?", (r["id"],))
        conn.execute("DELETE FROM session_exercises WHERE session_id = ?", (r["id"],))
    conn.execute("DELETE FROM sessions WHERE split_id = ?", (split_id,))
    for r in conn.execute("SELECT id FROM exercises WHERE split_id = ?", (split_id,)).fetchall():
        conn.execute("DELETE FROM sets WHERE exercise_id = ?", (r["id"],))
        conn.execute("DELETE FROM session_exercises WHERE exercise_id = ?", (r["id"],))
    conn.execute("DELETE FROM exercises WHERE split_id = ?", (split_id,))
    conn.execute("DELETE FROM splits WHERE id = ?", (split_id,))
    conn.commit()


def update_exercise(conn, exercise_id, **fields):
    """Edit an exercise in place. Logged sets keep pointing at it, so a rename or
    a corrected step size applies to history as well."""
    name = (fields.get("name") or "").strip()
    if not name:
        return "Name can't be empty."
    split_id = fields.get("split_id")
    clash = conn.execute(
        "SELECT id FROM exercises WHERE split_id = ? AND name = ? COLLATE NOCASE AND id != ?",
        (split_id, name, exercise_id),
    ).fetchone()
    if clash:
        return f"That split already has an exercise called {name}."
    mode = fields.get("weight_mode") or "added"
    if mode not in ("added", "assisted", "none"):
        mode = "added"
    conn.execute(
        """
        UPDATE exercises SET split_id = ?, muscle_group = ?, name = ?, name_ja = ?,
               target_sets = ?, target_rep_range = ?, step_kg = ?,
               uses_weight = ?, weight_mode = ?
        WHERE id = ?
        """,
        (split_id, (fields.get("muscle_group") or "Other").strip(), name,
         (fields.get("name_ja") or "").strip() or None,
         fields.get("target_sets"), fields.get("target_rep_range"),
         fields.get("step_kg"), 0 if mode == "none" else 1, mode, exercise_id),
    )
    conn.commit()
    return None


def exercise_usage(conn, exercise_id):
    return conn.execute(
        "SELECT COUNT(*) AS sets FROM sets WHERE exercise_id = ?", (exercise_id,)
    ).fetchone()


def delete_exercise(conn, exercise_id):
    conn.execute("DELETE FROM sets WHERE exercise_id = ?", (exercise_id,))
    conn.execute("DELETE FROM session_exercises WHERE exercise_id = ?", (exercise_id,))
    conn.execute("DELETE FROM exercises WHERE id = ?", (exercise_id,))
    conn.commit()

# ---- CSV import ----

def _unescape_csv(value):
    """Undo the leading apostrophe the export adds to formula-looking values."""
    text = (value or "").strip()
    if text[:2] in ("'=", "'+", "'-", "'@"):
        return text[1:]
    return text


def import_sets_csv(conn, user_id, rows):
    """Load rows produced by the CSV export back in, for the given user.

    Splits, exercises and sessions named in the file are created if they don't
    exist. A set already present for the same date, exercise and set number is
    skipped, so importing the same file twice doesn't duplicate anything.

    `rows` is an iterable of dicts (csv.DictReader). Returns a summary dict.
    """
    added = skipped = 0
    errors = []
    split_cache, exercise_cache, session_cache = {}, {}, {}

    for i, row in enumerate(rows, start=2):        # row 1 is the header
        try:
            date_str = _unescape_csv(row.get("date"))
            split_name = _unescape_csv(row.get("split")) or "Imported"
            ex_name = _unescape_csv(row.get("exercise"))
            muscle = _unescape_csv(row.get("muscle_group")) or "Other"
            reps_raw = (row.get("reps") or "").strip()
            if not date_str or not ex_name or not reps_raw:
                errors.append(f"row {i}: needs date, exercise and reps")
                continue
            reps = int(float(reps_raw))
            weight_raw = (row.get("weight_kg") or "").strip()
            weight = float(weight_raw) if weight_raw else None
            set_number = int(float(row.get("set_number") or 0)) or None

            if split_name not in split_cache:
                split_cache[split_name] = create_split(conn, split_name)
            split_id = split_cache[split_name]

            ex_key = (split_id, ex_name)
            if ex_key not in exercise_cache:
                found = conn.execute(
                    "SELECT id FROM exercises WHERE name = ? COLLATE NOCASE", (ex_name,)
                ).fetchone()
                exercise_cache[ex_key] = found["id"] if found else create_exercise(
                    conn, split_id, muscle, ex_name, 3, "8-12", 2.5,
                    uses_weight=weight is not None,
                )
            exercise_id = exercise_cache[ex_key]

            sess_key = (date_str, split_id)
            if sess_key not in session_cache:
                found = conn.execute(
                    "SELECT id FROM sessions WHERE user_id = ? AND date = ? AND split_id = ?",
                    (user_id, date_str, split_id),
                ).fetchone()
                if found:
                    session_cache[sess_key] = found["id"]
                else:
                    cur = conn.execute(
                        "INSERT INTO sessions (user_id, split_id, date, notes, finished_at) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (user_id, split_id, date_str,
                         _unescape_csv(row.get("session_notes")) or None, date_str),
                    )
                    session_cache[sess_key] = cur.lastrowid
            session_id = session_cache[sess_key]

            if set_number is not None:
                dupe = conn.execute(
                    "SELECT id FROM sets WHERE session_id = ? AND exercise_id = ? AND set_number = ?",
                    (session_id, exercise_id, set_number),
                ).fetchone()
                if dupe:
                    skipped += 1
                    continue
            else:
                set_number = conn.execute(
                    "SELECT COALESCE(MAX(set_number), 0) + 1 AS n FROM sets "
                    "WHERE session_id = ? AND exercise_id = ?",
                    (session_id, exercise_id),
                ).fetchone()["n"]

            conn.execute(
                "INSERT INTO sets (session_id, exercise_id, set_number, weight_kg, reps) "
                "VALUES (?, ?, ?, ?, ?)",
                (session_id, exercise_id, set_number, weight, reps),
            )
            conn.execute(
                "INSERT OR IGNORE INTO session_exercises (session_id, exercise_id, sort_order) "
                "VALUES (?, ?, 0)",
                (session_id, exercise_id),
            )
            added += 1
        except (ValueError, TypeError) as exc:
            errors.append(f"row {i}: {exc}")

    conn.commit()
    return {"added": added, "skipped": skipped, "errors": errors}


# ---- whole-database backup ----

def backup_database(dest_path):
    """Write a consistent copy of the database, safe to run while it's in use.

    Uses SQLite's own backup API rather than copying the file, so a write landing
    mid-copy can't produce a torn snapshot. Local/dev only -- see
    dump_database_sql() for the Workers/D1 equivalent, which has no file to copy.
    """
    src = sqlite3.connect(DB_PATH)
    dest = sqlite3.connect(dest_path)
    try:
        src.backup(dest)
    finally:
        dest.close()
        src.close()
    return dest_path


_BACKUP_TABLES = ("users", "splits", "exercises", "sessions", "session_exercises", "sets")


def dump_database_sql(conn):
    """Plain-SQL export of every row in every table, newest-safe INSERT order
    (parents before children). D1 has no file to copy the way sqlite3.backup()
    does, so `/export.db` on Workers ships this instead of a binary .db file --
    restorable with `sqlite3 new.db < dump.sql` after loading schema.sql first."""
    lines = ["PRAGMA foreign_keys=OFF;"]
    for table in _BACKUP_TABLES:
        rows = conn.execute(f"SELECT * FROM {table}").fetchall()
        for row in rows:
            cols = list(row.keys())
            values = ", ".join(_sql_literal(row[c]) for c in cols)
            lines.append(f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({values});")
    return "\n".join(lines) + "\n"


def _sql_literal(value):
    if value is None:
        return "NULL"
    if isinstance(value, (int, float)):
        return repr(value)
    return "'" + str(value).replace("'", "''") + "'"


# ---- bilingual display names ----

def _field(row, key):
    """Read a column that may not be present on this row. sqlite3.Row raises
    IndexError for an unknown key rather than returning None."""
    try:
        return row[key]
    except (KeyError, IndexError, TypeError):
        return None


def display_name(row, lang="en"):
    """The Japanese name when there is one and the app is in Japanese, else the
    English one.

    Accepts any row naming a split or an exercise, whether its columns arrived as
    `name`/`name_ja` or were aliased by a join to `split_name`/`split_name_ja`.
    """
    for ja_key, en_key in (("name_ja", "name"),
                           ("split_name_ja", "split_name"),
                           ("exercise_name_ja", "exercise_name")):
        english = _field(row, en_key)
        if english is None:
            continue
        if lang == "ja":
            japanese = _field(row, ja_key)
            if japanese:
                return japanese
        return english
    return ""


def set_user_lang(conn, user_id, lang):
    conn.execute("UPDATE users SET lang = ? WHERE id = ?", (lang, user_id))
    conn.commit()
