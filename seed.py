"""One-time (idempotent) seed script: populates splits and exercises.

Safe to re-run -- every insert is skip-if-exists by unique name.
Run via `python seed.py` (or via `init_db.py`, which also applies schema.sql first).

Splits are the three categories: Push, Pull, Legs. Each holds the full pool of
exercises for that category; a session pre-loads the pool and you prune it.

Every entry carries a Japanese name so the app reads properly in either language.
`weight_mode` is 'added' for normal loading, 'assisted' for machines where less
weight is the harder effort, and 'none' for bodyweight.
"""
from models import get_db

# (split_name, split_name_ja, [exercises])
# exercise = (muscle_group, name, name_ja, sets, rep_range, step_kg, weight_mode)
SPLITS = [
    ("Push", "プッシュ", [
        ("Chest", "Bench", "ベンチプレス", 3, "5-8", 2.5, "added"),
        ("Chest", "Bench backoff", "ベンチ バックオフ", 1, "8-12", 2.5, "added"),
        ("Chest", "Incline bench", "インクラインベンチ", 3, "8-12", 2.5, "added"),
        ("Chest", "Bench smith", "スミスベンチ", 3, "12-15", 2.5, "added"),
        ("Chest", "Incline smith/dumbbell", "インクライン スミス/ダンベル", 3, "12-15", 2.5, "added"),
        ("Chest", "Fly machine", "フライマシン", 3, "12-20", 1.25, "added"),
        ("Chest", "Machine flies", "マシンフライ", 3, "12-20", 1.25, "added"),
        ("Shoulders", "OHP", "オーバーヘッドプレス", 3, "12-15", 2.5, "added"),
        ("Shoulders", "OHP smith", "スミス オーバーヘッドプレス", 2, "5-8", 2.5, "added"),
        ("Shoulders", "OHP backoff", "OHP バックオフ", 1, "8-12", 2.5, "added"),
        ("Shoulders", "Lateral raise", "サイドレイズ", 3, "12-20", 1.0, "added"),
        ("Triceps", "Cable pushdowns", "ケーブルプレスダウン", 3, "12-20", 1.25, "added"),
        ("Triceps", "Pushdown machine", "プレスダウンマシン", 3, "12-20", 1.25, "added"),
        ("Triceps", "Skullcrushers", "スカルクラッシャー", 3, "12-20", 1.25, "added"),
        ("Chest", "Assisted dips", "アシストディップス", 3, "8-12", 2.5, "assisted"),
    ]),
    ("Pull", "プル", [
        ("Back", "Weighted pullups", "加重懸垂", 3, "8-12", 2.5, "added"),
        ("Back", "Pullups", "懸垂", 3, "8-12", 2.5, "none"),
        ("Back", "Assisted pullups", "アシスト懸垂", 3, "8-12", 2.5, "assisted"),
        ("Back", "Straight arm pulldowns", "ストレートアームプルダウン", 3, "12-20", 1.25, "added"),
        ("Back", "Barbell row", "バーベルロウ", 3, "8-12", 2.5, "added"),
        ("Back", "Cable row", "ケーブルロウ", 3, "12-20", 1.25, "added"),
        ("Back", "Lat machine", "ラットプルダウン", 3, "12-15", 1.25, "added"),
        ("Back", "Shrugs", "シュラッグ", 3, "12-15", 1.25, "added"),
        ("Back", "Back shrugs", "バックシュラッグ", 3, "12-15", 1.25, "added"),
        ("Biceps", "Strict curl", "ストリクトカール", 3, "8-10", 1.25, "added"),
        ("Biceps", "Hammer curl", "ハンマーカール", 3, "8-12", 1.25, "added"),
        ("Biceps", "Cable hammer curl", "ケーブルハンマーカール", 3, "8-12", 1.25, "added"),
        ("Biceps", "Preacher curl", "プリーチャーカール", 3, "12-20", 1.25, "added"),
        ("Biceps", "Concentration curl", "コンセントレーションカール", 3, "12-20", 1.25, "added"),
        ("Shoulders", "Rear delts", "リアデルト", 3, "12-20", 1.0, "added"),
        ("Shoulders", "Face pulls", "フェイスプル", 3, "12-20", 1.25, "added"),
    ]),
    ("Legs", "レッグ", [
        ("Quads", "Squat", "スクワット", 2, "5-8", 2.5, "added"),
        ("Quads", "Squat backoff", "スクワット バックオフ", 1, "8-12", 2.5, "added"),
        ("Quads", "Lunges", "ランジ", 3, "12-20", 1.25, "added"),
        ("Quads", "Leg extensions", "レッグエクステンション", 3, "12-20", 1.25, "added"),
        ("Quads", "Leg press", "レッグプレス", 3, "12-20", 2.5, "added"),
        ("Hamstrings", "Leg curl", "レッグカール", 3, "8-12", 1.25, "added"),
        ("Hamstrings", "Hamstring curls", "ハムストリングカール", 3, "15-20", 1.25, "added"),
        ("Hamstrings", "Goodmornings", "グッドモーニング", 3, "8-12", 2.5, "added"),
        ("Hamstrings", "Back extension", "バックエクステンション", 3, "12-20", 1.25, "added"),
        ("Glutes", "Hip thrust", "ヒップスラスト", 3, "8-12", 2.5, "added"),
        ("Glutes", "Glute kickbacks", "キックバック", 3, "12-20", 1.25, "added"),
        ("Calves", "Calves", "カーフ", 3, "12-20", 1.25, "added"),
        ("Calves", "Calf raise", "カーフレイズ", 3, "15-20", 1.25, "added"),
    ]),
]


def seed(conn):
    # No users are seeded: accounts are created by signing in with a new name.
    for split_order, (split_name, split_ja, exercises) in enumerate(SPLITS):
        conn.execute(
            "INSERT OR IGNORE INTO splits (name, name_ja, sort_order) VALUES (?, ?, ?)",
            (split_name, split_ja, split_order),
        )
        # Fill in the Japanese name for a split seeded before it had one.
        conn.execute(
            "UPDATE splits SET name_ja = ? WHERE name = ? AND (name_ja IS NULL OR name_ja = '')",
            (split_ja, split_name),
        )
        split_id = conn.execute(
            "SELECT id FROM splits WHERE name = ?", (split_name,)
        ).fetchone()["id"]

        for sort_order, (muscle, name, name_ja, sets_, reps, step, mode) in enumerate(exercises):
            conn.execute(
                """
                INSERT OR IGNORE INTO exercises
                    (split_id, muscle_group, name, name_ja, target_sets, target_rep_range,
                     step_kg, sort_order, uses_weight, weight_mode)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (split_id, muscle, name, name_ja, sets_, reps, step, sort_order,
                 0 if mode == "none" else 1, mode),
            )
            # Backfill for rows seeded before these columns existed.
            conn.execute(
                "UPDATE exercises SET name_ja = ? "
                "WHERE split_id = ? AND name = ? AND (name_ja IS NULL OR name_ja = '')",
                (name_ja, split_id, name),
            )

    conn.commit()


if __name__ == "__main__":
    conn = get_db()
    seed(conn)
    conn.close()
    print("Seed complete.")
