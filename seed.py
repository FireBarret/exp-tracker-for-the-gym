"""Seed script: syncs splits and exercises from SPLITS below into the DB.

Edit SPLITS directly to add, rename, or retune an exercise/split, then re-run
this (see "Applying edits" below) -- it's an upsert keyed on name, so existing
rows get updated in place rather than duplicated, and nothing already in a
workout history breaks (sessions/sets reference exercises by id, which never
changes for an existing name). Deleting an entry here does NOT delete it from
the DB -- remove it from the app's Manage screen if you want it gone.

Run locally via `python seed.py` (or via `init_db.py`, which also applies
schema.sql first). To apply an edit to the live site, generate SQL from this
file and run it against the remote D1 database:

    python3 -c "import seed; seed.print_sql()" | \\
        npx wrangler d1 execute gym-tracker --remote --file=/dev/stdin

Every entry carries a Japanese name so the app reads properly in either
language. `weight_mode` is 'added' for normal loading, 'assisted' for
machines where less weight is the harder effort, and 'none' for bodyweight
(no weight recorded at all).
"""
from models import get_db

# (split_name, split_name_ja, [exercises])
# exercise = (muscle_group, name, name_ja, sets, rep_range, step_kg, weight_mode)
SPLITS = [
    ('Push', 'プッシュ', [
        ('Chest', 'Bench', 'ベンチプレス', 3, '5-8', 2.5, 'added'),
        ('Chest', 'Bench backoff', 'ベンチ バックオフ', 1, '8-12', 2.5, 'added'),
        ('Chest', 'Incline bench', 'インクラインベンチ', 3, '8-12', 2.5, 'added'),
        ('Chest', 'Bench smith', 'スミスベンチ', 3, '12-15', 2.5, 'added'),
        ('Chest', 'Incline smith/dumbbell', 'インクライン スミス/ダンベル', 3, '12-15', 2.5, 'added'),
        ('Chest', 'Fly machine', 'フライマシン', 3, '12-20', 1.25, 'added'),
        ('Chest', 'Machine flies', 'マシンフライ', 3, '12-20', 1.25, 'added'),
        ('Shoulders', 'OHP', 'オーバーヘッドプレス', 3, '12-15', 2.5, 'added'),
        ('Shoulders', 'OHP smith', 'スミス オーバーヘッドプレス', 2, '5-8', 2.5, 'added'),
        ('Shoulders', 'OHP backoff', 'OHP バックオフ', 1, '8-12', 2.5, 'added'),
        ('Shoulders', 'Lateral raise', 'サイドレイズ', 3, '12-20', 1.0, 'added'),
        ('Triceps', 'Cable pushdowns', 'ケーブルプレスダウン', 3, '12-20', 1.25, 'added'),
        ('Triceps', 'Pushdown machine', 'プレスダウンマシン', 3, '12-20', 1.25, 'added'),
        ('Triceps', 'Skullcrushers', 'スカルクラッシャー', 3, '12-20', 1.25, 'added'),
        ('Chest', 'Dips(Assisted)', 'アシスト・ディップ', 3, '8-12', 2.5, 'added'),
        ('Abs', 'Abs (incline bench)', '腹筋(インクライン・ベンチ)', 3, '20', 2.5, 'none'),
    ]),
    ('Pull', 'プル', [
        ('Back', 'Weighted pullups', '加重懸垂', 3, '8-12', 2.5, 'added'),
        ('Back', 'Pullups', '懸垂', 3, '8-12', 2.5, 'none'),
        ('Back', 'Straight arm pulldowns', 'ストレートアームプルダウン', 3, '12-20', 1.25, 'added'),
        ('Back', 'Barbell row', 'バーベルロウ', 3, '8-12', 2.5, 'added'),
        ('Back', 'Cable row', 'ケーブルロウ', 3, '12-20', 1.25, 'added'),
        ('Back', 'Lat machine', 'ラットプルダウン', 3, '12-15', 7.0, 'added'),
        ('Back', 'Shrugs', 'シュラッグ', 3, '12-15', 1.25, 'added'),
        ('Back', 'Back shrugs', 'バックシュラッグ', 3, '12-15', 1.25, 'added'),
        ('Biceps', 'Strict curl', 'ストリクトカール', 3, '8-10', 1.25, 'added'),
        ('Biceps', 'Hammer curl', 'ハンマーカール', 3, '8-12', 1.25, 'added'),
        ('Biceps', 'Cable hammer curl', 'ケーブルハンマーカール', 3, '8-12', 1.25, 'added'),
        ('Biceps', 'Preacher curl', 'プリーチャーカール', 3, '12-20', 1.25, 'added'),
        ('Biceps', 'Concentration curl', 'コンセントレーションカール', 3, '12-20', 1.25, 'added'),
        ('Shoulders', 'Rear delts', 'リアデルト', 3, '12-20', 1.0, 'added'),
        ('Shoulders', 'Face pulls', 'フェイスプル', 3, '12-20', 1.25, 'added'),
        ('Back', 'Assisted Pullup', 'チンニング　アシスト', 3, '8-12', 2.5, 'assisted'),
        ('Other', 'Back Extensions', 'バック-エクステンション', 3, '12-15', 2.5, 'none'),
    ]),
    ('Legs', 'レッグ', [
        ('Quads', 'Squat', 'スクワット', 2, '5-8', 2.5, 'added'),
        ('Quads', 'Squat backoff', 'スクワット バックオフ', 1, '8-12', 2.5, 'added'),
        ('Quads', 'Lunges', 'ランジ', 3, '12-20', 1.25, 'added'),
        ('Quads', 'Leg extensions', 'レッグエクステンション', 3, '12-20', 1.25, 'added'),
        ('Quads', 'Leg press', 'レッグプレス', 3, '12-20', 2.5, 'added'),
        ('Hamstrings', 'Leg curl', 'レッグカール', 3, '8-12', 1.25, 'added'),
        ('Hamstrings', 'Hamstring curls', 'ハムストリングカール', 3, '15-20', 1.25, 'added'),
        ('Hamstrings', 'Goodmornings', 'グッドモーニング', 3, '8-12', 2.5, 'added'),
        ('Hamstrings', 'Back extension', 'バックエクステンション', 3, '12-20', 1.25, 'added'),
        ('Glutes', 'Hip thrust', 'ヒップスラスト', 3, '8-12', 2.5, 'added'),
        ('Glutes', 'Glute kickbacks', 'キックバック', 3, '12-20', 1.25, 'added'),
        ('Calves', 'Calves', 'カーフ', 3, '12-20', 1.25, 'added'),
        ('Calves', 'Calf raise', 'カーフレイズ', 3, '15-20', 1.25, 'added'),
    ]),
    ('Full Body 1', '全身 1', [
        ('Chest', 'Chest Press', 'チェスト　プレス', 3, '8-12', 5.0, 'added'),
        ('Back', 'Assisted Pull-ups', 'チンニング・アシスト', 3, '8-12', 2.5, 'assisted'),
        ('Chest', 'Chest Extension', 'チェスト エクステンション', 3, '8-12', 2.5, 'added'),
        ('Legs', 'Leg Press', 'レッグ・プレス', 3, '8-12', 2.5, 'added'),
        ('Other', 'Abs Machine', '腹筋　マシン', 3, '8-12', 2.5, 'added'),
    ]),
    ('Full Body 2', '全身2', [
        ('Chest', 'Chest Press', 'チェスト-プレス', 3, '8-12', 2.5, 'added'),
        ('Back', 'Lat machine', 'ラット-マシーン', 3, '8-12', 2.5, 'added'),
        ('Back', 'Back Extension', 'バック-エクステンション', 3, '8-12', 2.5, 'none'),
        ('Other', 'Incline Abs', '腹筋(インクライン)', 3, '8-12', 2.5, 'none'),
        ('背中', 'row', 'ロー', 3, '8-12', 2.5, 'added'),
        ('Legs', 'Hip adductor', 'ヒップアッだクター(↔️)', 3, '8-12', 2.5, 'added'),
        ('Legs', 'Hip abduction', 'ヒップアブダクター(➡️⬅️)', 3, '8-12', 2.5, 'added'),
    ]),
]


def seed(conn):
    # No users are seeded: accounts are created by signing in with a new name.
    for split_order, (split_name, split_ja, exercises) in enumerate(SPLITS):
        conn.execute(
            """
            INSERT INTO splits (name, name_ja, sort_order) VALUES (?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                name_ja = excluded.name_ja,
                sort_order = excluded.sort_order
            """,
            (split_name, split_ja, split_order),
        )
        split_id = conn.execute(
            "SELECT id FROM splits WHERE name = ?", (split_name,)
        ).fetchone()["id"]

        for sort_order, (muscle, name, name_ja, sets_, reps, step, mode) in enumerate(exercises):
            conn.execute(
                """
                INSERT INTO exercises
                    (split_id, muscle_group, name, name_ja, target_sets, target_rep_range,
                     step_kg, sort_order, uses_weight, weight_mode)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(split_id, name) DO UPDATE SET
                    muscle_group = excluded.muscle_group,
                    name_ja = excluded.name_ja,
                    target_sets = excluded.target_sets,
                    target_rep_range = excluded.target_rep_range,
                    step_kg = excluded.step_kg,
                    sort_order = excluded.sort_order,
                    uses_weight = excluded.uses_weight,
                    weight_mode = excluded.weight_mode
                """,
                (split_id, muscle, name, name_ja, sets_, reps, step, sort_order,
                 0 if mode == "none" else 1, mode),
            )
    conn.commit()


def print_sql():
    """Emit the same upserts as plain SQL, for `wrangler d1 execute --remote`.

    Splits are looked up by name via a subselect rather than a captured id,
    since the id isn't known until the INSERT above actually runs against
    the target database.
    """
    def q(s):
        return "NULL" if s is None else "'" + str(s).replace("'", "''") + "'"

    lines = []
    for split_order, (split_name, split_ja, exercises) in enumerate(SPLITS):
        lines.append(
            f"INSERT INTO splits (name, name_ja, sort_order) "
            f"VALUES ({q(split_name)}, {q(split_ja)}, {split_order}) "
            f"ON CONFLICT(name) DO UPDATE SET name_ja=excluded.name_ja, "
            f"sort_order=excluded.sort_order;"
        )
        for sort_order, (muscle, name, name_ja, sets_, reps, step, mode) in enumerate(exercises):
            uses_weight = 0 if mode == "none" else 1
            lines.append(
                "INSERT INTO exercises "
                "(split_id, muscle_group, name, name_ja, target_sets, target_rep_range, "
                "step_kg, sort_order, uses_weight, weight_mode) "
                f"SELECT id, {q(muscle)}, {q(name)}, {q(name_ja)}, {sets_}, {q(reps)}, "
                f"{step}, {sort_order}, {uses_weight}, {q(mode)} "
                f"FROM splits WHERE name = {q(split_name)} "
                "ON CONFLICT(split_id, name) DO UPDATE SET "
                "muscle_group=excluded.muscle_group, name_ja=excluded.name_ja, "
                "target_sets=excluded.target_sets, target_rep_range=excluded.target_rep_range, "
                "step_kg=excluded.step_kg, sort_order=excluded.sort_order, "
                "uses_weight=excluded.uses_weight, weight_mode=excluded.weight_mode;"
            )
    print("\n".join(lines))


if __name__ == "__main__":
    conn = get_db()
    seed(conn)
    conn.close()
    print("Seed complete.")
