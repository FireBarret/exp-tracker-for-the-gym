# Gym Log

Multi-user workout logging webapp. Pick **Push / Pull / Legs** → the session loads
that split's exercises → tap one → set the weight and reps with big +/− buttons →
**Add set**. Plus history and a progress chart per exercise.

Stack: Flask + SQLite (plain `sqlite3`, no ORM) + server-rendered templates +
vanilla JS. No build step, no dependencies beyond Flask.

Available in English and Japanese.

## How it works

- **Signing in** is a name plus one shared password. The password is the same for
  everyone — it exists only to keep strangers off the site, not to separate
  accounts. Typing a name nobody has used creates an account for it, so a new
  person just signs in. Existing names show as chips to tap.
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
- **Weight modes**: an exercise is one of *added weight* (normal — more kg is a
  stronger set), *assisted* (assistance machines, where **less** kg is the harder
  set, so PBs and the progress chart track the minimum instead of the maximum),
  or *bodyweight only* (reps, no kg at all).
- **Two languages**: English and 日本語, switchable from the header or the Manage
  page. The choice is saved per account, so two people sharing the app each get
  their own. Exercises and splits carry both an English and an optional Japanese
  name — the seeded ones have both, and the add/edit forms have a field for each.
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
- **The set screen is not a separate page** — it opens over the plan instantly
  from data already loaded. Its URL still updates, so refreshing or sharing a
  link works, the browser back button returns to the plan, and with JavaScript
  off the link falls back to a server-rendered page.
- **Manage** (in the nav) is where you rename or delete accounts, rename or
  delete splits, and edit any exercise — its name, muscle group, split, target
  sets and reps, step size, and whether it uses weight at all. Renaming keeps
  every logged set attached, so history and PBs follow the new name.
- **Exporting**: the **⬇ Export CSV** button on the History page downloads one
  row per set (date, split, muscle group, exercise, set number, weight, reps,
  notes). It respects whatever split/exercise filter is active, so you can export
  everything or just one lift. You only ever export your own history.
- **Importing**: **⬆ Import CSV** takes a file in that same shape back in.
  Splits and exercises named in the file are created if missing, and a set
  that's already there (same date, exercise and set number) is skipped — so
  importing twice doesn't duplicate anything. Everything lands in the signed-in
  account, whatever the file's `user` column says.
- **Full backup**: **⬇ Download full backup (.db)** hands you the whole SQLite
  database — every account, every set. It's taken through SQLite's backup API,
  so it's a consistent snapshot even if someone is logging a set at the time.
  To restore, replace `gym.db` on the server with the downloaded file (Files tab
  on PythonAnywhere) and reload the web app.

## Performance

The host is slow to answer, so the app is built to ask it as little as possible.

- **Logging costs no page loads.** The session page ships the data for every
  exercise on the plan (previous, PB, target, sets so far — about 2.5KB of JSON),
  and the set screen is rendered from that in the browser. Opening an exercise,
  going back, and switching between exercises are all instant and make zero
  requests. The only thing that talks to the server during a workout is the
  actual write when you add or delete a set. A whole workout is one page load
  plus one small POST per set, where it used to be a full page load each way for
  every exercise.
- **Static files are fetched once, ever.** Every asset URL carries a hash of its
  contents (`style.css?v=a6b7b9af1e`) and is served with a one-year immutable
  cache, so the browser never re-requests it — not even a 304, which still costs
  a full round trip on a slow host. Changing a file changes its URL, so deploys
  still take effect immediately.
- **A service worker precaches the shell** (CSS + JS) and keeps the last version
  of each page you've visited. Repeat visits render without waiting on the
  server, and a dropped signal still shows the last state instead of an error.
  It never caches writes or the CSV export.
- **No CDN.** The progress chart is ~5KB of inline SVG rather than a ~200KB
  charting library, so there's no third-party round trip and the page works on a
  bad connection.
- **Installable.** There's a web app manifest, so "Add to Home Screen" gives you
  a full-screen icon with no browser chrome — which, combined with the service
  worker, makes it open instantly.

Total assets: ~8.5KB gzipped, downloaded once. A session page is ~2.8KB gzipped.

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

No accounts are seeded — the first person to sign in creates theirs by typing a
name. Names can be changed later on the **Manage** page.

## Upgrading an existing database

Most schema changes apply themselves. On startup the app adds any missing
columns or tables to `gym.db` (these changes are purely additive, so they can't
lose data) — a deploy that adds a column no longer takes the site down while you
remember to run a command.

The one exception is the original six-split layout (Push 1 / Push 2 / Legs 1 / …),
which has to rewrite rows and takes a backup first, so it stays deliberate. If
your database still has it, every page shows a banner saying so. Run it once:

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
```
Then hit **Reload** on the Web tab. Your `.env` and `gym.db` are untouched by
pulls, and any additive schema changes apply themselves on the first request.

If something looks wrong after a deploy, `https://YOUR_USERNAME.pythonanywhere.com/healthz`
reports whether the database is reachable, whether a manual migration is
outstanding, and row counts for each table.

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
