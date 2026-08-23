# Gym Log

Two-user workout logging webapp. Pick **Push / Pull / Legs** → the session loads
that split's exercises → tap one → set the weight and reps with big +/− buttons →
**Add set**. Plus history and a progress chart per exercise.

Stack: Flask + SQLite (plain `sqlite3`, no ORM) + server-rendered templates +
vanilla JS + Chart.js (via CDN). No build step.

## How it works

- **Splits** are the three categories: Push, Pull, Legs. Each holds the full pool
  of exercises for that category. You can add your own splits too.
- **Starting a session** pre-loads that split's whole exercise pool. Prune what
  you're not doing with the `×` on each row, or add more with **+ Add exercise**
  (that split's remaining exercises first, then `···` for everything else, then
  a form to invent a brand new exercise).
- **The set screen** shows *Previous* and *PB* for that exercise — tap either to
  load its numbers. Weight and reps are both big; tap one to make it the active
  number that the `−0.5 / +2.5 / +5 / +10` buttons drive (reps use `−1 / +1 / +2 / +5`).
  Tap the number that's already active to type an exact value.
- **Exercises are shared** between both users, but *Previous*, *PB*, history and
  progress are all per-user.
- **Bodyweight exercises** (`uses_weight = 0`, e.g. Pullups) show reps only — no kg.
- **Abs / cardio** go in the free-text Notes box at the bottom of the session.
- **Resuming**: a workout stays in progress until you tap **Finish workout**, so
  closing the tab (or your phone locking) loses nothing. The splits screen shows
  a *Workout in progress* card with a **Resume** button, and a green Resume pill
  sits in the nav from any page. Only one workout is open at a time — starting a
  different split finishes the previous one first. Finished sessions can be put
  back into progress with **Reopen** on the History page.
- **Editing history**: every session on the History page has an **Edit** link —
  change its date and notes, correct any set's weight or reps, delete individual
  sets (the rest renumber), or delete the whole session. Clearing a weight field
  turns that set into a bodyweight set.
- **Exporting**: the **⬇ Export CSV** button on the History page downloads one
  row per set (date, split, muscle group, exercise, set number, weight, reps,
  notes). It respects whatever split/exercise filter is active, so you can export
  everything or just one lift. You only ever export your own history.

## Local development

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# edit .env: set GYM_APP_PASSWORD (or leave blank to skip the login gate in dev)

python init_db.py     # creates gym.db from schema.sql and seeds splits/exercises
flask run              # http://127.0.0.1:5000
```

`init_db.py` is safe to re-run — the schema uses `CREATE TABLE IF NOT EXISTS`
and the seed skips anything that already exists by name.

Rename the two seeded users ("Dariush", "Partner") by editing `USERS` in
`seed.py` before first running `init_db.py`, or afterwards with
`sqlite3 gym.db "UPDATE users SET name = '...' WHERE id = 1;"`.

## Upgrading an existing database

If you already have a `gym.db` from the original six-split version
(Push 1 / Push 2 / Legs 1 / …), run the migration once:

```bash
source venv/bin/activate      # on PythonAnywhere: workon gym-env
python migrate.py
```

It backs up your database first (`gym.db.bak-<timestamp>`), collapses the six
splits into three, and copies every session and set across by exercise name, so
no logged workouts are lost. It's safe to run twice — the second run reports
"already migrated" and does nothing.

## Deploying to PythonAnywhere (free tier)

1. Push this repo to GitHub.
2. On PythonAnywhere, open a **Bash console** and clone it:
   ```bash
   git clone https://github.com/FireBarret/exp-tracker-for-the-gym.git
   cd exp-tracker-for-the-gym
   ```
3. Create a virtualenv and install deps (the Python version here must match the
   one you pick on the Web tab in step 5):
   ```bash
   mkvirtualenv --python=/usr/bin/python3.10 gym-env
   pip install -r requirements.txt
   ```
4. Create your `.env` (this file is gitignored, so `git pull` never touches it —
   you only do this once):
   ```bash
   cp .env.example .env
   nano .env      # set GYM_APP_PASSWORD and FLASK_SECRET_KEY
   ```
5. **Web tab** → "Add a new web app" → Manual configuration → **Python 3.10**.
6. Set:
   - **Source code** and **Working directory**: `/home/YOUR_USERNAME/exp-tracker-for-the-gym`
   - **Virtualenv**: `/home/YOUR_USERNAME/.virtualenvs/gym-env`
   - **Static files**: URL `/static/` → Directory `/home/YOUR_USERNAME/exp-tracker-for-the-gym/static`
7. Click the **WSGI configuration file** link and replace its whole contents with
   the contents of `wsgi_template.py` from this repo, with your username filled in.
8. Initialize the database once:
   ```bash
   workon gym-env
   cd ~/exp-tracker-for-the-gym
   python init_db.py
   ```
9. Hit **Reload** on the Web tab, then visit `https://YOUR_USERNAME.pythonanywhere.com`.
10. Free PythonAnywhere accounts go dormant if you don't log in to
    pythonanywhere.com at least every 3 months — no other maintenance needed.

### Updating after the first deploy

```bash
workon gym-env
cd ~/exp-tracker-for-the-gym
git pull
pip install -r requirements.txt   # only if requirements changed
python migrate.py                  # applies any schema changes; safe to run every time
```
Then hit **Reload** on the Web tab. Your `.env` and `gym.db` are untouched by pulls.

## Notes

- `gym.db` and `.env` are gitignored — each environment keeps its own.
- Removing an exercise from a session also deletes the sets you logged for it
  in that session (it asks first). Same for deleting a session from the edit
  screen — it asks, then takes its sets with it.
- The CSV export prefixes any value starting with `=`, `+`, `-` or `@` with an
  apostrophe, so a creatively named exercise can't run as a spreadsheet formula.
- Since `gym.db` lives on PythonAnywhere's disk and isn't in git, the CSV export
  doubles as your backup — worth pulling one down every so often.
- Finishing a workout you logged nothing into simply discards it rather than
  leaving an empty session in your history. A workout left open for more than a
  day stops offering to resume (it just becomes ordinary history), so a session
  started late at night can still be resumed the next morning.
