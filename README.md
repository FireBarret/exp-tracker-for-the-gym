# Gym Log

Two-user workout logging webapp. Pick a split → tap an exercise → one-tap
"Repeat" / "+step" weight buttons based on last time → log reps. Also has
history and a progress chart per exercise.

Stack: Flask + SQLite (plain `sqlite3`, no ORM) + server-rendered templates +
vanilla JS + Chart.js (via CDN). No build step.

## Local development

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# edit .env: set GYM_APP_PASSWORD (or leave blank to skip the login gate in dev)

python init_db.py     # creates gym.db from schema.sql and seeds users/splits/exercises
flask run              # http://127.0.0.1:5000
```

`init_db.py` is safe to re-run — the schema uses `CREATE TABLE IF NOT EXISTS`
and the seed skips any user/split/exercise that already exists by name.

Rename the two seeded users ("Dariush", "Partner") by editing `USERS` in
`seed.py` before first running `init_db.py`, or update the `users` table
directly with `sqlite3 gym.db "UPDATE users SET name = '...' WHERE id = ...;"`.

## Deploying to PythonAnywhere (free tier)

1. Push this repo to GitHub (already done if you're reading this from there).
2. On PythonAnywhere: open a **Bash console** and clone it:
   ```bash
   git clone https://github.com/FireBarret/exp-tracker-for-the-gym.git
   cd exp-tracker-for-the-gym
   ```
3. Create a virtualenv and install deps:
   ```bash
   mkvirtualenv --python=/usr/bin/python3.10 gym-env
   pip install -r requirements.txt
   ```
4. **Web tab** → "Add a new web app" → Manual configuration → matching Python version.
5. Set:
   - **Source code**: `/home/YOUR_USERNAME/exp-tracker-for-the-gym`
   - **Working directory**: same path
   - **Virtualenv**: path to the `gym-env` virtualenv PythonAnywhere just showed you
   - **Static files**: URL `/static/` → Directory `/home/YOUR_USERNAME/exp-tracker-for-the-gym/static`
6. Open the WSGI configuration file linked on the Web tab and replace its
   contents with `wsgi_template.py` from this repo, filling in your username.
   Prefer setting `GYM_APP_PASSWORD` and `FLASK_SECRET_KEY` as real environment
   variables in the Web tab's "Environment variables" section instead of
   editing the WSGI file directly, if your plan supports that.
7. Back in the Bash console, initialize the database once:
   ```bash
   workon gym-env
   python init_db.py
   ```
8. Hit **Reload** on the Web tab. Visit `https://YOUR_USERNAME.pythonanywhere.com`.
9. Free PythonAnywhere accounts go dormant if you don't log in to
   pythonanywhere.com at least every 3 months — no other maintenance needed.

## Notes

- `gym.db` is not committed (gitignored) — each environment (your laptop,
  PythonAnywhere) has its own database file, created via `init_db.py`.
- Bodyweight-only exercises (e.g. plain pull-ups) can be logged with no
  weight — just leave the custom-weight field blank, or use the
  "Log (bodyweight / first time)" button that appears before any weight has
  been recorded for that exercise.
- Abs/cardio isn't part of the tap-to-log flow — use the free-text **Notes**
  field at the bottom of the log page for that.
