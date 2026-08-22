"""One-time (idempotent) seed script: populates users, splits, and exercises.

Safe to re-run -- every insert is skip-if-exists by unique name.
Run via `python seed.py` (or via `init_db.py`, which also applies schema.sql first).
"""
from models import get_db, init_schema

USERS = ["Dariush", "Partner"]

# (split_name, [ (muscle_group, name, target_sets, target_rep_range, step_kg), ... ])
SPLITS = [
    ("Push 1", [
        ("Chest", "Bench", 3, "5-8", 2.5),
        ("Chest", "Backoff set", 1, "8-12", 2.5),
        ("Chest", "Incline bench", 3, "8-12", 2.5),
        ("Chest", "Fly machine", 3, "12-20", 1.25),
        ("Shoulders", "OHP", 3, "12-15", 2.5),
        ("Shoulders", "Lateral raise", 3, "12-20", 1.0),
        ("Triceps", "Cable pushdowns", 3, "12-20", 1.25),
        ("Triceps", "Skullcrushers", 3, "12-20", 1.25),
    ]),
    ("Push 2", [
        ("Shoulders", "OHP smith", 2, "5-8", 2.5),
        ("Shoulders", "Backoff set", 1, "8-12", 2.5),
        ("Shoulders", "Lateral raise", 3, "12-20", 1.0),
        ("Chest", "Bench smith", 3, "12-15", 2.5),
        ("Chest", "Incline smith/dumbbell", 3, "12-15", 2.5),
        ("Chest", "Machine flies", 3, "12-20", 1.25),
        ("Triceps", "Cable pushdowns", 3, "12-20", 1.25),
        ("Triceps", "Pushdown machine", 3, "12-20", 1.25),
        ("Triceps", "Skullcrushers", 3, "12-20", 1.25),
    ]),
    ("Legs 1", [
        ("Quads", "Squat", 2, "5-8", 2.5),
        ("Quads", "Backoff set", 1, "8-12", 2.5),
        ("Quads", "Lunges", 3, "12-20", 1.25),
        ("Quads", "Leg extensions", 3, "12-20", 1.25),
        ("Hamstrings", "Leg curl", 3, "8-12", 1.25),
        ("Hamstrings", "Back extension", 3, "12-20", 1.25),
        ("Hamstrings", "Calves", 3, "12-20", 1.25),
    ]),
    ("Legs 2", [
        ("Glutes", "Hip thrust", 3, "8-12", 2.5),
        ("Glutes", "Glute kickbacks", 3, "12-20", 1.25),
        ("Hamstrings", "Goodmornings", 3, "8-12", 2.5),
        ("Hamstrings", "Hamstring curls", 3, "15-20", 1.25),
        ("Quads", "Leg press", 3, "12-20", 2.5),
        ("Quads", "Calf raise", 3, "15-20", 1.25),
    ]),
    ("Pull 1", [
        ("Back", "Weighted pullups", 3, "8-12", 2.5),
        ("Back", "Straight arm pulldowns", 3, "12-20", 1.25),
        ("Back", "Barbell row", 3, "12-15", 2.5),
        ("Back", "Shrugs", 3, "12-15", 1.25),
        ("Biceps", "Strict curl", 3, "8-10", 1.25),
        ("Biceps", "Hammer curl", 3, "8-12", 1.25),
        ("Biceps", "Preacher curl", 3, "12-20", 1.25),
        ("Shoulders", "Rear delts", 3, "12-20", 1.0),
    ]),
    ("Pull 2", [
        ("Back", "Barbell rows", 3, "8-12", 2.5),
        ("Back", "Cable row", 3, "12-20", 1.25),
        ("Back", "Lat machine", 3, "12-15", 1.25),
        ("Back", "Back shrugs", 3, "12-15", 1.25),
        ("Biceps", "Strict curl", 3, "8-10", 1.25),
        ("Biceps", "Cable hammer curl", 3, "8-12", 1.25),
        ("Biceps", "Concentration curl", 3, "12-20", 1.25),
        ("Shoulders", "Face pulls", 3, "12-20", 1.25),
    ]),
]


def seed(conn):
    for name in USERS:
        conn.execute("INSERT OR IGNORE INTO users (name) VALUES (?)", (name,))

    for split_name, exercises in SPLITS:
        conn.execute("INSERT OR IGNORE INTO splits (name) VALUES (?)", (split_name,))
        split_row = conn.execute(
            "SELECT id FROM splits WHERE name = ?", (split_name,)
        ).fetchone()
        split_id = split_row["id"]

        for sort_order, (muscle_group, name, target_sets, rep_range, step_kg) in enumerate(exercises):
            exists = conn.execute(
                "SELECT 1 FROM exercises WHERE split_id = ? AND name = ?",
                (split_id, name),
            ).fetchone()
            if exists:
                continue
            conn.execute(
                """
                INSERT INTO exercises
                    (split_id, muscle_group, name, target_sets, target_rep_range, step_kg, sort_order)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (split_id, muscle_group, name, target_sets, rep_range, step_kg, sort_order),
            )

    conn.commit()


if __name__ == "__main__":
    conn = get_db()
    seed(conn)
    conn.close()
    print("Seed complete.")
