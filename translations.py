"""UI strings in English and Japanese.

A plain dictionary rather than gettext/Babel: there are a couple of hundred
strings, the app has no build step, and .mo compilation on PythonAnywhere would
be one more thing to remember on deploy.

Exercise and split names are NOT here -- those live in the database (`name` and
`name_ja`), because the user can add their own.
"""

LANGUAGES = {"en": "English", "ja": "日本語"}
DEFAULT_LANG = "en"

UI = {
    # nav / chrome
    "app.name":            ("Gym Log", "ジムログ"),
    "nav.splits":          ("Splits", "スプリット"),
    "nav.history":         ("History", "履歴"),
    "nav.progress":        ("Progress", "記録"),
    "nav.manage":          ("Manage", "管理"),
    "nav.signout":         ("Sign out", "サインアウト"),
    "nav.resume":          ("Resume {split}", "{split} を再開"),

    # sign in
    "login.name":          ("Your name", "お名前"),
    "login.password":      ("Password", "パスワード"),
    "login.continue":      ("Continue", "つづける"),
    "login.tap_name":      ("Tap a name to fill it in:", "名前をタップして入力:"),
    "login.new_account":   ("A name that isn't listed creates a new account.",
                            "登録されていない名前を入れると、新しいアカウントを作成します。"),
    "login.err_password":  ("Wrong password.", "パスワードが違います。"),
    "login.err_name":      ("Enter a name.", "名前を入力してください。"),
    "login.err_long":      ("That name is too long.", "名前が長すぎます。"),
    "login.welcome":       ("Welcome, {name} — your account is ready.",
                            "ようこそ {name} さん — アカウントを作成しました。"),

    # splits / starting a workout
    "splits.heading":      ("Hey {name} — what are you training?",
                            "{name} さん、今日はどこを鍛えますか？"),
    "splits.in_progress":  ("Workout in progress", "進行中のワークアウト"),
    "splits.resume":       ("Resume", "再開"),
    "splits.finish":       ("Finish", "終了"),
    "splits.sets_logged":  ("{n} sets logged", "{n} セット記録済み"),
    "splits.switch_note":  ("Starting a different split below will finish this one first.",
                            "別のスプリットを始めると、こちらは終了になります。"),
    "splits.confirm_finish": ("Finish this {split} workout?",
                              "この {split} のワークアウトを終了しますか？"),
    "splits.new":          ("+ New split", "+ 新しいスプリット"),
    "splits.new_ph":       ("e.g. Arms, Full body", "例: 腕、全身"),
    "splits.create":       ("Create", "作成"),

    # the session plan
    "session.empty":       ("Nothing on the plan yet. Tap + Add exercise to build this session.",
                            "まだ種目がありません。「+ 種目を追加」で組み立てましょう。"),
    "session.add":         ("+ Add exercise", "+ 種目を追加"),
    "session.finish":      ("Finish workout", "ワークアウトを終了"),
    "session.reopen":      ("Reopen workout", "ワークアウトを再開"),
    "session.finished_on": ("Finished on {when}.", "{when} に終了しました。"),
    "session.confirm_finish": ("Finish this workout? You can reopen it later from History.",
                               "ワークアウトを終了しますか？履歴からいつでも再開できます。"),
    "session.confirm_remove": ("Remove {name} from this session?",
                               "この日のメニューから {name} を外しますか？"),
    "session.bodyweight":  ("bodyweight", "自重"),
    "session.notes":       ("Notes", "メモ"),
    "session.notes_hint":  ("(abs / cardio / anything else)", "（腹筋・有酸素など）"),
    "session.notes_ph":    ("e.g. 3x15 hanging leg raise, 10 min bike",
                            "例: レッグレイズ 3x15、バイク10分"),
    "session.save_notes":  ("Save notes", "メモを保存"),
    "session.saved":       ("Saved.", "保存しました。"),

    # the set entry screen
    "entry.previous":      ("Previous", "前回"),
    "entry.pb":            ("PB", "自己ベスト"),
    "entry.weight":        ("Weight", "重量"),
    "entry.reps":          ("Reps", "回数"),
    "entry.unit_kg":       ("kg", "kg"),
    "entry.unit_reps":     ("reps", "回"),
    "entry.assist":        ("Assist", "アシスト"),
    "entry.assist_hint":   ("Assistance machine — less weight is the harder set, so PBs go down.",
                            "アシストマシン — 重量が軽いほど高強度。自己ベストは数値が小さいほど上です。"),
    "entry.add_set":       ("Add set", "セットを追加"),
    "entry.this_session":  ("This session", "今回のセット"),
    "entry.no_sets":       ("No sets logged yet.", "まだセットがありません。"),
    "entry.prompt_weight": ("Weight in kg", "重量 (kg)"),
    "entry.prompt_reps":   ("Reps", "回数"),
    "entry.save_failed":   ("Couldn't save that set — check your connection.",
                            "セットを保存できませんでした。通信を確認してください。"),

    # adding an exercise
    "add.title":           ("Add exercise", "種目を追加"),
    "add.recommended":     ("Recommended for {split}", "{split} のおすすめ"),
    "add.all_on_plan":     ("Everything from {split} is already on the plan.",
                            "{split} の種目はすべて追加済みです。"),
    "add.others":          ("··· Other exercises ({n})", "··· ほかの種目 ({n})"),
    "add.brand_new":       ("+ Brand new exercise", "+ 新しい種目を作る"),
    "add.name_en":         ("Exercise name (English)", "種目名（英語）"),
    "add.name_ja":         ("Exercise name (日本語)", "種目名（日本語）"),
    "add.name_ja_hint":    ("Optional — shown when the app is in Japanese.",
                            "任意 — 日本語表示のときに使われます。"),
    "add.muscle":          ("Muscle group", "部位"),
    "add.split":           ("Split", "スプリット"),
    "add.target_sets":     ("Target sets", "目標セット数"),
    "add.rep_range":       ("Rep range", "目標レップ数"),
    "add.step":            ("Step (kg)", "刻み (kg)"),
    "weight.added":        ("Added weight", "重量あり"),
    "weight.assisted":     ("Assisted — less is stronger", "アシスト — 少ないほど高強度"),
    "weight.none":         ("Bodyweight only", "自重のみ"),
    "add.weight_mode":     ("Weight", "重量の種類"),
    "add.create":          ("Create & add", "作成して追加"),

    # history
    "history.title":       ("History", "履歴"),
    "history.all_splits":  ("All splits", "すべてのスプリット"),
    "history.all_exercises": ("All exercises", "すべての種目"),
    "history.export_csv":  ("⬇ Export CSV", "⬇ CSVを書き出す"),
    "history.export_filtered": ("⬇ Export CSV (filtered)", "⬇ CSVを書き出す（絞り込み）"),
    "history.import_csv":  ("⬆ Import CSV", "⬆ CSVを読み込む"),
    "history.full_backup": ("⬇ Full backup", "⬇ 全データのバックアップ"),
    "history.empty":       ("No sessions yet. Go log something — or bring history in from a file.",
                            "まだ記録がありません。記録するか、ファイルから読み込みましょう。"),
    "history.in_progress": ("in progress", "進行中"),
    "history.resume":      ("Resume", "再開"),
    "history.reopen":      ("Reopen", "再開する"),
    "history.edit":        ("Edit", "編集"),
    "history.no_sets":     ("No sets logged.", "セットの記録はありません。"),
    "history.col_exercise": ("Exercise", "種目"),
    "history.col_set":     ("Set", "セット"),
    "history.col_weight":  ("Weight", "重量"),
    "history.col_reps":    ("Reps", "回数"),

    # editing a past session
    "edit.title":          ("Edit session", "記録を編集"),
    "edit.date":           ("Date", "日付"),
    "edit.notes":          ("Notes", "メモ"),
    "edit.sets":           ("Sets", "セット"),
    "edit.save":           ("Save changes", "変更を保存"),
    "edit.delete_session": ("Delete entire session", "この記録をすべて削除"),
    "edit.no_sets":        ("No sets logged in this session.", "この記録にはセットがありません。"),
    "edit.confirm_set":    ("Delete this set?", "このセットを削除しますか？"),
    "edit.confirm_session": ("Delete this whole session and all {n} of its sets? This cannot be undone.",
                             "この記録と {n} セットをすべて削除しますか？元に戻せません。"),

    # progress
    "progress.title":      ("Progress", "記録"),
    "progress.pick":       ("Pick an exercise…", "種目を選んでください…"),
    "progress.pick_hint":  ("Pick an exercise above to see your progress.",
                            "上から種目を選ぶと推移が表示されます。"),
    "progress.none":       ("No logged sets for this exercise yet.",
                            "この種目の記録はまだありません。"),
    "progress.no_weighted": ("No weighted sets logged for this exercise yet.",
                             "この種目には重量ありの記録がまだありません。"),

    # manage
    "manage.title":        ("Manage", "管理"),
    "manage.accounts":     ("Accounts", "アカウント"),
    "manage.save":         ("Save", "保存"),
    "manage.signed_in":    ("signed in", "サインイン中"),
    "manage.account_meta": ("{sessions} sessions, {sets} sets", "{sessions} 回、{sets} セット"),
    "manage.delete_account": ("Delete account", "アカウントを削除"),
    "manage.confirm_account": ("Delete {name} and all {n} of their sessions? This cannot be undone.",
                               "{name} と {n} 件の記録をすべて削除しますか？元に戻せません。"),
    "manage.splits":       ("Splits & exercises", "スプリットと種目"),
    "manage.split_meta":   ("{exercises} exercises, {sessions} sessions",
                            "{exercises} 種目、{sessions} 回"),
    "manage.no_exercises": ("No exercises in this split.", "このスプリットには種目がありません。"),
    "manage.delete_split": ("Delete split", "スプリットを削除"),
    "manage.confirm_split": ("Delete the {name} split, its {exercises} exercise(s) and {sessions} logged session(s)? This cannot be undone.",
                             "{name} スプリットと、{exercises} 種目・{sessions} 件の記録を削除しますか？元に戻せません。"),
    "manage.edit":         ("edit ›", "編集 ›"),
    "manage.data":         ("Data", "データ"),
    "manage.data_hint":    ("Back up everything, or bring history in from a CSV.",
                            "全データをバックアップ、またはCSVから読み込みます。"),
    "manage.download_db":  ("⬇ Download full backup (.db)", "⬇ 全データをダウンロード (.db)"),
    "manage.language":     ("Language", "言語"),

    # editing an exercise
    "exedit.title":        ("Edit exercise", "種目を編集"),
    "exedit.name_en":      ("Name (English)", "名前（英語）"),
    "exedit.name_ja":      ("Name (日本語)", "名前（日本語）"),
    "exedit.muscle":       ("Muscle", "部位"),
    "exedit.muscle_new":   ("+ Add a new option", "+ 新しい部位を追加"),
    "exedit.muscle_new_placeholder": ("New muscle group name", "新しい部位名"),
    "exedit.split":        ("Splits", "スプリット"),
    "exedit.sets":         ("Sets", "セット数"),
    "exedit.reps":         ("Reps", "回数"),
    "exedit.step":         ("Step (kg)", "刻み (kg)"),
    "exedit.uses_weight":  ("Uses weight (uncheck for bodyweight-only)",
                            "重量を使う（自重のみの場合はオフ）"),
    "exedit.save":         ("Save changes", "変更を保存"),
    "exedit.usage":        ("{n} logged sets use this exercise. Renaming it keeps them attached, so history and PBs follow the new name.",
                            "この種目には {n} セットの記録があります。名前を変えても記録はそのまま引き継がれます。"),
    "exedit.delete":       ("Delete exercise", "種目を削除"),
    "exedit.confirm":      ("Delete {name} and its {n} logged set(s)? This cannot be undone.",
                            "{name} と {n} セットの記録を削除しますか？元に戻せません。"),

    # import
    "import.title":        ("Import CSV", "CSVを読み込む"),
    "import.button":       ("Import", "読み込む"),
    "import.added":        ("{n} sets imported.", "{n} セットを読み込みました。"),
    "import.skipped":      ("{n} already present, so skipped.", "{n} 件はすでにあるためスキップしました。"),
    "import.errors":       ("{n} row(s) couldn't be read:", "{n} 行を読み込めませんでした:"),
    "import.and_more":     ("…and {n} more", "…ほか {n} 件"),
    "import.see_history":  ("See history", "履歴を見る"),
    "import.choose_file":  ("Choose a CSV file first.", "先にCSVファイルを選んでください。"),
    "import.not_csv":      ("That doesn't look like a text CSV file.",
                            "テキストのCSVファイルではないようです。"),
    "import.missing_cols": ("That file is missing required column(s): {cols}",
                            "必要な列がありません: {cols}"),
    "import.expects":      ("What it expects", "必要な形式"),
    "import.expects_body": ("The same shape the Export CSV button produces. Required columns are date, exercise and reps; split, muscle_group, set_number, weight_kg and session_notes are used when present.",
                            "「CSVを書き出す」と同じ形式です。必須の列は date、exercise、reps。split、muscle_group、set_number、weight_kg、session_notes があれば使われます。"),
    "import.target":       ("Everything is imported into {name}'s history, whatever the user column says. Splits and exercises named in the file are created if they don't exist yet. A set that's already there — same date, exercise and set number — is skipped, so importing the same file twice doesn't duplicate anything. An empty weight_kg means a bodyweight set.",
                            "すべて {name} の履歴に読み込まれます（user 列の内容に関わらず）。ファイル内のスプリットや種目がなければ作成します。同じ日付・種目・セット番号の記録はスキップされるので、同じファイルを2回読み込んでも重複しません。weight_kg が空欄なら自重セットです。"),

    # schema warning
    "schema.warning":      ("This database still uses the old six-split layout. Run python migrate.py in a Bash console, then reload the web app.",
                            "データベースが古い形式のままです。Bashコンソールで python migrate.py を実行し、アプリを再読み込みしてください。"),
}

# Muscle groups are free text (custom exercises can invent one), so an unknown
# value simply falls through to itself.
MUSCLE_GROUPS = {
    "Chest": "胸", "Shoulders": "肩", "Triceps": "三頭", "Back": "背中",
    "Biceps": "二頭", "Quads": "大腿四頭", "Hamstrings": "ハム",
    "Glutes": "臀部", "Calves": "ふくらはぎ", "Other": "その他",
}


def translate(key, lang=DEFAULT_LANG, **kwargs):
    entry = UI.get(key)
    if entry is None:
        return key                      # missing key shows itself, easy to spot
    text = entry[1] if lang == "ja" and len(entry) > 1 else entry[0]
    if not text:
        text = entry[0]
    return text.format(**kwargs) if kwargs else text


def muscle_group(name, lang=DEFAULT_LANG):
    if lang == "ja":
        return MUSCLE_GROUPS.get(name, name)
    return name
