"""One-time (idempotent) seed script: populates users, splits, and exercises.

Safe to re-run -- every insert is skip-if-exists by unique name.
Run via `python seed.py` (or via `init_db.py`, which also applies schema.sql first).

Splits are the three categories: Push, Pull, Legs. Each holds the full pool of
exercises for that category; a session pre-loads the pool and you prune it.
"""
from models import get_db

USERS = ["Dariush", "Partner"]

# (muscle_group, name, target_sets, target_rep_range, step_kg, uses_weight)
SPLITS = [
    ("Push", [
        ("Chest", "Bench", 3, "5-8", 2.5, 1),
        ("Chest", "Bench backoff", 1, "8-12", 2.5, 1),
        ("Chest", "Incline bench", 3, "8-12", 2.5, 1),
        ("Chest", "Bench smith", 3, "12-15", 2.5, 1),
        ("Chest", "Incline smith/dumbbell", 3, "12-15", 2.5, 1),
        ("Chest", "Fly machine", 3, "12-20", 1.25, 1),
        ("Chest", "Machine flies", 3, "12-20", 1.25, 1),
        ("Shoulders", "OHP", 3, "12-15", 2.5, 1),
        ("Shoulders", "OHP smith", 2, "5-8", 2.5, 1),
        ("Shoulders", "OHP backoff", 1, "8-12", 2.5, 1),
        ("Shoulders", "Lateral raise", 3, "12-20", 1.0, 1),
        ("Triceps", "Cable pushdowns", 3, "12-20", 1.25, 1),
        ("Triceps", "Pushdown machine", 3, "12-20", 1.25, 1),
        ("Triceps", "Skullcrushers", 3, "12-20", 1.25, 1),
    ]),
    ("Pull", [
        ("Back", "Weighted pullups", 3, "8-12", 2.5, 1),
        ("Back", "Pullups", 3, "8-12", 2.5, 0),
        ("Back", "Straight arm pulldowns", 3, "12-20", 1.25, 1),
        ("Back", "Barbell row", 3, "8-12", 2.5, 1),
        ("Back", "Cable row", 3, "12-20", 1.25, 1),
        ("Back", "Lat machine", 3, "12-15", 1.25, 1),
        ("Back", "Shrugs", 3, "12-15", 1.25, 1),
        ("Back", "Back shrugs", 3, "12-15", 1.25, 1),
        ("Biceps", "Strict curl", 3, "8-10", 1.25, 1),
        ("Biceps", "Hammer curl", 3, "8-12", 1.25, 1),
        ("Biceps", "Cable hammer curl", 3, "8-12", 1.25, 1),
        ("Biceps", "Preacher curl", 3, "12-20", 1.25, 1),
        ("Biceps", "Concentration curl", 3, "12-20", 1.25, 1),
        ("Shoulders", "Rear delts", 3, "12-20", 1.0, 1),
        ("Shoulders", "Face pulls", 3, "12-20", 1.25, 1),
    ]),
    ("Legs", [
        ("Quads", "Squat", 2, "5-8", 2.5, 1),
        ("Quads", "Squat backoff", 1, "8-12", 2.5, 1),
        ("Quads", "Lunges", 3, "12-20", 1.25, 1),
        ("Quads", "Leg extensions", 3, "12-20", 1.25, 1),
        ("Quads", "Leg press", 3, "12-20", 2.5, 1),
        ("Hamstrings", "Leg curl", 3, "8-12", 1.25, 1),
        ("Hamstrings", "Hamstring curls", 3, "15-20", 1.25, 1),
        ("Hamstrings", "Goodmornings", 3, "8-12", 2.5, 1),
        ("Hamstrings", "Back extension", 3, "12-20", 1.25, 1),
        ("Glutes", "Hip thrust", 3, "8-12", 2.5, 1),
        ("Glutes", "Glute kickbacks", 3, "12-20", 1.25, 1),
        ("Calves", "Calves", 3, "12-20", 1.25, 1),
        ("Calves", "Calf raise", 3, "15-20", 1.25, 1),
    ]),
]


def seed(conn):
    for name in USERS:
        conn.execute("INSERT OR IGNORE INTO users (name) VALUES (?)", (name,))

    for split_order, (split_name, exercises) in enumerate(SPLITS):
        conn.execute(
            "INSERT OR IGNORE INTO splits (name, sort_order) VALUES (?, ?)",
            (split_name, split_order),
        )
        split_id = conn.execute(
            "SELECT id FROM splits WHERE name = ?", (split_name,)
        ).fetchone()["id"]

        for sort_order, (muscle_group, name, sets_, reps, step, uses_weight) in enumerate(exercises):
            conn.execute(
                """
                INSERT OR IGNORE INTO exercises
                    (split_id, muscle_group, name, target_sets, target_rep_range,
                     step_kg, sort_order, uses_weight)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (split_id, muscle_group, name, sets_, reps, step, sort_order, uses_weight),
            )

    conn.commit()


if __name__ == "__main__":
    conn = get_db()
    seed(conn)
    conn.close()
    print("Seed complete.")
