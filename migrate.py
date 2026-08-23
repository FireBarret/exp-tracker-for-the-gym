"""Migrate an existing gym.db from the old 6-split schema to the new one.

What changed: the six numbered splits (Push 1/2, Legs 1/2, Pull 1/2) collapse into
three (Push, Pull, Legs), exercises gained `uses_weight`/`is_custom`, and sessions
now carry an explicit exercise plan in `session_exercises`.

Rather than patching the old tables in place (the new schema adds a UNIQUE
constraint, which SQLite can't add to a live table), this rebuilds the database
and copies your data across, matching exercises by NAME so nothing is lost. Any
exercise name that no longer exists in the seed is recreated as a custom exercise.

Usage:  python migrate.py
A timestamped backup is written next to gym.db before anything is touched.
"""
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from models import DB_PATH, ensure_schema_current, get_db, init_schema
from seed import seed

# Old split name -> new split name
SPLIT_MAP = {
    "Push 1": "Push", "Push 2": "Push",
    "Pull 1": "Pull", "Pull 2": "Pull",
    "Legs 1": "Legs", "Legs 2": "Legs",
}

# "Backoff set" was ambiguous once the variants merged -- disambiguate by old split.
EXERCISE_RENAMES = {
    ("Push 1", "Backoff set"): "Bench backoff",
    ("Push 2", "Backoff set"): "OHP backoff",
    ("Legs 1", "Backoff set"): "Squat backoff",
    ("Pull 2", "Barbell rows"): "Barbell row",
}


def read_old(conn):
    """Pull every session and set out of the old database, keyed by name not id."""
    users = conn.execute("SELECT id, name FROM users").fetchall()
    sessions = conn.execute(
        """
        SELECT sessions.id, sessions.user_id, sessions.date,
               splits.name AS split_name,
               (SELECT notes FROM sessions s2 WHERE s2.id = sessions.id) AS notes
        FROM sessions JOIN splits ON splits.id = sessions.split_id
        """
    ).fetchall()
    sets = conn.execute(
        """
        SELECT sets.session_id, sets.set_number, sets.weight_kg, sets.reps,
               sets.created_at, exercises.name AS exercise_name,
               exercises.muscle_group, exercises.target_sets,
               exercises.target_rep_range, exercises.step_kg,
               splits.name AS split_name
        FROM sets
        JOIN exercises ON exercises.id = sets.exercise_id
        JOIN splits ON splits.id = exercises.split_id
        ORDER BY sets.session_id, sets.id
        """
    ).fetchall()
    return (
        [dict(r) for r in users],
        [dict(r) for r in sessions],
        [dict(r) for r in sets],
    )


def resolve_name(old_split, name):
    return EXERCISE_RENAMES.get((old_split, name), name)


def ensure_columns(conn):
    """Additive migrations, shared with the check the app runs on startup."""
    applied = ensure_schema_current(conn)
    for item in applied:
        print(f"  added {item}")
    return bool(applied)


def main():
    db = Path(DB_PATH)
    if not db.exists():
        print("No gym.db found -- nothing to migrate. Run `python init_db.py` instead.")
        return

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    has_session_exercises = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='session_exercises'"
    ).fetchone()
    split_names = {r["name"] for r in conn.execute("SELECT name FROM splits").fetchall()}
    if has_session_exercises and not (split_names & set(SPLIT_MAP)):
        changed = ensure_columns(conn)
        conn.close()
        print("Schema updated." if changed else "Database already up to date -- nothing to do.")
        return

    users, sessions, sets = read_old(conn)
    conn.close()

    backup = db.with_suffix(".db.bak-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
    shutil.copy2(db, backup)
    print(f"Backed up existing database to {backup.name}")

    db.unlink()
    init_schema()
    new = get_db()
    seed(new)

    # users -- keep their original ids so nothing else has to be remapped
    old_user_names = {u["id"]: u["name"] for u in users}
    for u in users:
        new.execute("INSERT OR IGNORE INTO users (id, name) VALUES (?, ?)", (u["id"], u["name"]))

    split_ids = {r["name"]: r["id"] for r in new.execute("SELECT id, name FROM splits").fetchall()}

    def exercise_id_for(row):
        """Find the new exercise by name, creating a custom one if the seed dropped it."""
        name = resolve_name(row["split_name"], row["exercise_name"])
        new_split = SPLIT_MAP.get(row["split_name"], row["split_name"])
        found = new.execute("SELECT id FROM exercises WHERE name = ?", (name,)).fetchone()
        if found:
            return found["id"]
        split_id = split_ids.get(new_split) or list(split_ids.values())[0]
        order = new.execute(
            "SELECT COALESCE(MAX(sort_order), 0) + 1 AS n FROM exercises WHERE split_id = ?",
            (split_id,),
        ).fetchone()["n"]
        cur = new.execute(
            """INSERT INTO exercises (split_id, muscle_group, name, target_sets,
                    target_rep_range, step_kg, sort_order, uses_weight, is_custom)
               VALUES (?, ?, ?, ?, ?, ?, ?, 1, 1)""",
            (split_id, row["muscle_group"] or "Other", name, row["target_sets"],
             row["target_rep_range"], row["step_kg"] or 2.5, order),
        )
        print(f"  recreated dropped exercise as custom: {name}")
        return cur.lastrowid

    # sessions -- remapped onto the three new splits
    session_id_map = {}
    for s in sessions:
        new_split = SPLIT_MAP.get(s["split_name"], s["split_name"])
        split_id = split_ids.get(new_split)
        if split_id is None:
            split_id = new.execute(
                "INSERT INTO splits (name, sort_order, is_custom) VALUES (?, 99, 1)",
                (new_split,),
            ).lastrowid
            split_ids[new_split] = split_id
        cur = new.execute(
            "INSERT INTO sessions (user_id, split_id, date, notes) VALUES (?, ?, ?, ?)",
            (s["user_id"], split_id, s["date"], s.get("notes")),
        )
        session_id_map[s["id"]] = cur.lastrowid

    # sets -- matched by exercise name, renumbered per exercise
    counters = {}
    for st in sets:
        new_session = session_id_map.get(st["session_id"])
        if new_session is None:
            continue
        ex_id = exercise_id_for(st)
        key = (new_session, ex_id)
        counters[key] = counters.get(key, 0) + 1
        new.execute(
            """INSERT INTO sets (session_id, exercise_id, set_number, weight_kg, reps, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (new_session, ex_id, counters[key], st["weight_kg"], st["reps"], st["created_at"]),
        )

    # rebuild each old session's plan from the exercises it actually logged
    for (session_id, ex_id) in counters:
        new.execute(
            "INSERT OR IGNORE INTO session_exercises (session_id, exercise_id, sort_order) VALUES (?, ?, 0)",
            (session_id, ex_id),
        )

    # everything carried over is history, not a workout still in progress
    new.execute("UPDATE sessions SET finished_at = date WHERE finished_at IS NULL")

    new.commit()
    n_users = new.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
    n_sess = new.execute("SELECT COUNT(*) c FROM sessions").fetchone()["c"]
    n_sets = new.execute("SELECT COUNT(*) c FROM sets").fetchone()["c"]
    new.close()

    print(f"Migrated: {n_users} users, {n_sess} sessions, {n_sets} sets.")
    print(f"If anything looks wrong, restore with:  cp {backup.name} gym.db")


if __name__ == "__main__":
    main()
