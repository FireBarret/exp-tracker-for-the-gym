import csv
import hashlib
import io
import os
from datetime import date
from functools import wraps

from flask import (Flask, Response, abort, g, jsonify, make_response,
                   redirect, render_template, request, session, url_for)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import models

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-me")

APP_PASSWORD = os.environ.get("GYM_APP_PASSWORD")


@app.template_filter("trim_zeros")
def trim_zeros(value):
    """60.0 -> '60', 62.5 -> '62.5'. Keeps weights readable on the big display."""
    if value is None:
        return ""
    text = f"{float(value):g}"
    return text


# ---- schema check on startup ----
#
# A deploy that adds a column shouldn't take the site down until someone
# remembers to run migrate.py, so additive changes are applied here at import.
# The one migration that rewrites data (six splits to three) is not automatic;
# if it's still outstanding, every page says so instead of throwing a 500.

SCHEMA_NEEDS_MIGRATION = False

def _check_schema():
    global SCHEMA_NEEDS_MIGRATION
    try:
        conn = models.get_db()
        try:
            applied = models.ensure_schema_current(conn)
            if applied:
                app.logger.info("Applied schema updates: %s", ", ".join(applied))
            SCHEMA_NEEDS_MIGRATION = models.needs_full_migration(conn)
        finally:
            conn.close()
    except Exception:
        # Never let a schema probe stop the app from booting.
        app.logger.exception("Schema check failed")

_check_schema()


@app.route("/healthz")
def healthz():
    """Plain-text status, handy when a deploy misbehaves."""
    try:
        conn = models.get_db()
        counts = {
            t: conn.execute(f"SELECT COUNT(*) c FROM {t}").fetchone()["c"]
            for t in ("users", "splits", "exercises", "sessions", "sets")
        }
        conn.close()
        return jsonify({"ok": True, "needs_full_migration": SCHEMA_NEEDS_MIGRATION,
                        "counts": counts})
    except Exception as exc:
        return jsonify({"ok": False, "error": f"{type(exc).__name__}: {exc}"}), 500


# ---- static assets: versioned URLs + long-lived caching ----
#
# PythonAnywhere's free tier is slow to answer, so the goal is to make the
# browser ask it as rarely as possible. Static files are served with a one-year
# immutable cache and a content-hash in the query string, so a changed file gets
# a new URL (and is refetched) while an unchanged one is never requested again --
# not even a 304 revalidation, which still costs a full round trip.

_ASSET_HASHES = {}


def asset_hash(filename):
    if app.debug:
        _ASSET_HASHES.pop(filename, None)
    if filename not in _ASSET_HASHES:
        path = os.path.join(app.static_folder, filename)
        try:
            with open(path, "rb") as f:
                _ASSET_HASHES[filename] = hashlib.md5(f.read()).hexdigest()[:10]
        except OSError:
            _ASSET_HASHES[filename] = "0"
    return _ASSET_HASHES[filename]


@app.template_global("static_url")
def static_url(filename):
    """url_for('static', ...) plus a content hash, so caching can be aggressive."""
    return url_for("static", filename=filename, v=asset_hash(filename))


@app.after_request
def add_cache_headers(response):
    if request.path.startswith("/static/"):
        if request.args.get("v"):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        else:
            response.headers["Cache-Control"] = "public, max-age=3600"
    return response


# ---- PWA: service worker + manifest ----
#
# The worker is served from the root so its scope covers the whole app, and it's
# rendered rather than static so the fingerprinted asset list can be baked in.

PRECACHE_ASSETS = ["style.css", "session.js", "set_entry.js", "chart.js"]


@app.route("/sw.js")
def service_worker():
    urls = [static_url(f) for f in PRECACHE_ASSETS]
    version = hashlib.md5("".join(urls).encode()).hexdigest()[:10]
    resp = make_response(render_template("sw.js", version=version, precache=urls))
    resp.headers["Content-Type"] = "application/javascript"
    resp.headers["Cache-Control"] = "no-cache"      # always check for a new worker
    return resp


@app.route("/manifest.webmanifest")
def manifest():
    resp = jsonify({
        "name": "Gym Log",
        "short_name": "Gym Log",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "background_color": "#0f1115",
        "theme_color": "#0f1115",
        "icons": [{
            "src": url_for("static", filename="icon.svg"),
            "sizes": "any",
            "type": "image/svg+xml",
            "purpose": "any maskable",
        }],
    })
    resp.headers["Cache-Control"] = "public, max-age=86400"
    return resp


@app.context_processor
def inject_schema_warning():
    return {"schema_needs_migration": SCHEMA_NEEDS_MIGRATION}


@app.context_processor
def inject_active_session():
    """Every page can offer a way back into an unfinished workout."""
    if not session.get("authed") or not session.get("user_id"):
        return {}
    db = getattr(g, "db", None)
    if db is None:
        return {}
    return {"active_session": models.get_active_session(db, session["user_id"])}


# ---- db lifecycle ----

@app.before_request
def open_db():
    g.db = models.get_db()


@app.teardown_appcontext
def close_db(exception=None):
    db = getattr(g, "db", None)
    if db is not None:
        db.close()


# ---- auth ----

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("authed"):
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def user_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("home"))
        return view(*args, **kwargs)
    return wrapped


def owned_session(session_id):
    """Fetch a session, 404ing unless it belongs to the logged-in user."""
    sess = models.get_session(g.db, session_id)
    if not sess or sess["user_id"] != session["user_id"]:
        abort(404)
    return sess


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        # If no password is configured, don't lock the owner out -- treat as open (dev mode).
        if not APP_PASSWORD or request.form.get("password") == APP_PASSWORD:
            session["authed"] = True
            return redirect(request.args.get("next") or url_for("home"))
        error = "Wrong password."
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---- user + split picking ----

@app.route("/")
@login_required
def home():
    return render_template("home.html", users=models.get_users(g.db))


@app.route("/user/<int:user_id>/select")
@login_required
def select_user(user_id):
    user = models.get_user(g.db, user_id)
    if not user:
        abort(404)
    session["user_id"] = user_id
    session["user_name"] = user["name"]
    return redirect(url_for("splits"))


@app.route("/splits")
@login_required
@user_required
def splits():
    return render_template(
        "splits.html",
        splits=models.get_splits(g.db),
        resumable=models.get_active_session(g.db, session["user_id"]),
        user_name=session.get("user_name"),
    )


@app.route("/splits/new", methods=["POST"])
@login_required
@user_required
def new_split():
    name = (request.form.get("name") or "").strip()
    if not name:
        return redirect(url_for("splits"))
    models.create_split(g.db, name)
    return redirect(url_for("splits"))


@app.route("/session/start", methods=["POST"])
@login_required
@user_required
def start_session():
    split_id = request.form.get("split_id", type=int)
    if not split_id or not models.get_split(g.db, split_id):
        abort(400)
    session_id = models.create_session(
        g.db, session["user_id"], split_id, date.today().isoformat()
    )
    return redirect(url_for("session_log", session_id=session_id))


# ---- session plan (list of exercises) ----

@app.route("/session/<int:session_id>")
@login_required
@user_required
def session_log(session_id):
    sess = owned_session(session_id)
    split = models.get_split(g.db, sess["split_id"])
    # One batched fetch: the page ships this to the browser so the set screen
    # opens without another request.
    exercises = models.get_session_exercise_data(g.db, session["user_id"], session_id)

    grouped = {}
    for ex in exercises:
        grouped.setdefault(ex["muscle_group"], []).append(ex)

    return render_template(
        "session.html",
        session_row=sess,
        split=split,
        grouped=grouped,
        exercises_json=exercises,
        exercise_count=len(exercises),
        user_name=session.get("user_name"),
    )


@app.route("/session/<int:session_id>/add", methods=["GET", "POST"])
@login_required
@user_required
def add_exercise(session_id):
    sess = owned_session(session_id)

    if request.method == "POST":
        exercise_id = request.form.get("exercise_id", type=int)
        if exercise_id and models.get_exercise(g.db, exercise_id):
            models.add_exercise_to_session(g.db, session_id, exercise_id)
        return redirect(url_for("session_log", session_id=session_id))

    recommended, others = models.get_addable_exercises(g.db, session_id, sess["split_id"])
    return render_template(
        "add_exercise.html",
        session_row=sess,
        split=models.get_split(g.db, sess["split_id"]),
        recommended=recommended,
        others=others,
        splits=models.get_splits(g.db),
        user_name=session.get("user_name"),
    )


@app.route("/session/<int:session_id>/exercise/<int:exercise_id>/remove", methods=["POST"])
@login_required
@user_required
def remove_exercise(session_id, exercise_id):
    owned_session(session_id)
    models.remove_exercise_from_session(g.db, session_id, exercise_id)
    if request.is_json:
        return jsonify({"ok": True})
    return redirect(url_for("session_log", session_id=session_id))


@app.route("/session/<int:session_id>/exercise/new", methods=["POST"])
@login_required
@user_required
def new_exercise(session_id):
    """Create a brand new exercise type and drop it straight onto this session."""
    owned_session(session_id)
    name = (request.form.get("name") or "").strip()
    split_id = request.form.get("split_id", type=int)
    if not name or not split_id:
        return redirect(url_for("add_exercise", session_id=session_id))

    exercise_id = models.create_exercise(
        g.db,
        split_id=split_id,
        muscle_group=request.form.get("muscle_group") or "Other",
        name=name,
        target_sets=request.form.get("target_sets", type=int) or 3,
        target_rep_range=(request.form.get("target_rep_range") or "8-12").strip(),
        step_kg=request.form.get("step_kg", type=float) or 2.5,
        uses_weight=request.form.get("uses_weight") == "on",
    )
    models.add_exercise_to_session(g.db, session_id, exercise_id)
    return redirect(url_for("session_log", session_id=session_id))


@app.route("/session/<int:session_id>/finish", methods=["POST"])
@login_required
@user_required
def finish_session(session_id):
    owned_session(session_id)
    was_empty = models.finish_session(g.db, session_id)
    if was_empty:
        return redirect(url_for("splits"))
    return redirect(url_for("history"))


@app.route("/session/<int:session_id>/resume", methods=["POST"])
@login_required
@user_required
def resume_session(session_id):
    """Reopen a session that was finished (or auto-closed) so it can be added to."""
    owned_session(session_id)
    active = models.get_active_session(g.db, session["user_id"])
    if active and active["id"] != session_id:
        models.finish_session(g.db, active["id"])
    models.reopen_session(g.db, session_id)
    return redirect(url_for("session_log", session_id=session_id))


# ---- the set entry page (one page per exercise) ----

@app.route("/session/<int:session_id>/exercise/<int:exercise_id>")
@login_required
@user_required
def set_entry(session_id, exercise_id):
    owned_session(session_id)
    exercise = models.get_exercise(g.db, exercise_id)
    if not exercise:
        abort(404)

    user_id = session["user_id"]
    previous = models.get_last_set_for_exercise(g.db, user_id, exercise_id, session_id)
    pb = models.get_pb_for_exercise(g.db, user_id, exercise_id)
    logged = models.get_sets_for_exercise_in_session(g.db, session_id, exercise_id)

    # Seed the entry screen with the most sensible starting numbers: whatever was
    # done last in this session, else last workout, else a bare default.
    if logged:
        start_weight = logged[-1]["weight_kg"]
        start_reps = logged[-1]["reps"]
    elif previous:
        start_weight = previous["weight_kg"]
        start_reps = previous["reps"]
    else:
        start_weight = 20.0 if exercise["uses_weight"] else None
        start_reps = 10

    return render_template(
        "set_entry.html",
        session_row=models.get_session(g.db, session_id),
        exercise=exercise,
        previous=previous,
        pb=pb,
        logged=logged,
        start_weight=start_weight if start_weight is not None else 0.0,
        start_reps=start_reps,
        user_name=session.get("user_name"),
    )


@app.route("/session/<int:session_id>/log", methods=["POST"])
@login_required
@user_required
def log_set(session_id):
    owned_session(session_id)
    data = request.get_json(silent=True) or request.form

    exercise_id = data.get("exercise_id")
    weight_kg = data.get("weight_kg")
    reps = data.get("reps")

    if not exercise_id or reps in (None, ""):
        return jsonify({"error": "exercise_id and reps are required"}), 400

    exercise_id = int(exercise_id)
    exercise = models.get_exercise(g.db, exercise_id)
    if not exercise:
        return jsonify({"error": "unknown exercise"}), 400

    reps = int(reps)
    if weight_kg in (None, "", "null") or not exercise["uses_weight"]:
        weight_kg = None
    else:
        weight_kg = float(weight_kg)

    # Adding a set to an exercise that isn't on the plan puts it on the plan.
    models.add_exercise_to_session(g.db, session_id, exercise_id)
    set_id, set_number = models.log_set(g.db, session_id, exercise_id, weight_kg, reps)

    return jsonify({
        "ok": True,
        "set_id": set_id,
        "set_number": set_number,
        "set_count": models.get_set_count_for_exercise(g.db, session_id, exercise_id),
        "target_sets": exercise["target_sets"],
        "weight_kg": weight_kg,
        "reps": reps,
    })


@app.route("/session/<int:session_id>/set/<int:set_id>/delete", methods=["POST"])
@login_required
@user_required
def delete_set(session_id, set_id):
    owned_session(session_id)
    ok = models.delete_set(g.db, set_id, session_id)
    if request.is_json:
        return jsonify({"ok": ok})
    return redirect(request.referrer or url_for("session_log", session_id=session_id))


@app.route("/session/<int:session_id>/notes", methods=["POST"])
@login_required
@user_required
def session_notes(session_id):
    owned_session(session_id)
    if request.is_json:
        notes = (request.get_json(silent=True) or {}).get("notes", "")
    else:
        notes = request.form.get("notes", "")
    models.update_session_notes(g.db, session_id, notes)
    return jsonify({"ok": True})


# ---- history ----

@app.route("/history")
@login_required
@user_required
def history():
    split_id = request.args.get("split_id", type=int)
    exercise_id = request.args.get("exercise_id", type=int)
    sessions = models.get_sessions_for_user(g.db, session["user_id"], split_id, exercise_id)
    sessions_with_sets = [
        {"session": s, "sets": models.get_sets_for_session(g.db, s["id"])}
        for s in sessions
    ]
    return render_template(
        "history.html",
        sessions_with_sets=sessions_with_sets,
        all_splits=models.get_splits(g.db),
        all_exercises=models.get_all_exercise_names(g.db, session["user_id"]),
        selected_split_id=split_id,
        selected_exercise_id=exercise_id,
        user_name=session.get("user_name"),
    )


# ---- editing past sessions ----

@app.route("/history/session/<int:session_id>/edit", methods=["GET", "POST"])
@login_required
@user_required
def edit_session(session_id):
    sess = owned_session(session_id)

    if request.method == "POST":
        models.update_session(
            g.db,
            session_id,
            (request.form.get("date") or sess["date"]).strip(),
            request.form.get("notes", ""),
        )
        # Each set is submitted as set_<id>_weight / set_<id>_reps.
        for st in models.get_sets_for_session(g.db, session_id):
            reps = request.form.get(f"set_{st['id']}_reps", type=int)
            if reps is None or reps < 0:
                continue
            raw_weight = (request.form.get(f"set_{st['id']}_weight") or "").strip()
            weight = float(raw_weight) if raw_weight else None
            models.update_set(g.db, st["id"], session_id, weight, reps)
        return redirect(url_for("history"))

    return render_template(
        "edit_session.html",
        session_row=sess,
        split=models.get_split(g.db, sess["split_id"]),
        sets=models.get_sets_for_session(g.db, session_id),
        user_name=session.get("user_name"),
    )


@app.route("/history/session/<int:session_id>/delete", methods=["POST"])
@login_required
@user_required
def delete_session(session_id):
    owned_session(session_id)
    models.delete_session(g.db, session_id)
    return redirect(url_for("history"))


# ---- export ----

def _csv_safe(value):
    """Stop a value beginning with = + - @ from being read as a spreadsheet formula."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@") else text


@app.route("/export.csv")
@login_required
@user_required
def export_csv():
    rows = models.get_export_rows(
        g.db,
        session["user_id"],
        request.args.get("split_id", type=int),
        request.args.get("exercise_id", type=int),
    )

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["date", "user", "split", "muscle_group", "exercise",
                     "set_number", "weight_kg", "reps", "session_notes"])
    for r in rows:
        writer.writerow([
            _csv_safe(r["date"]), _csv_safe(r["user"]), _csv_safe(r["split"]),
            _csv_safe(r["muscle_group"]), _csv_safe(r["exercise"]),
            r["set_number"],
            "" if r["weight_kg"] is None else f"{r['weight_kg']:g}",
            r["reps"], _csv_safe(r["notes"]),
        ])

    filename = f"gym-log-{session.get('user_name', 'export')}-{date.today().isoformat()}.csv"
    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---- progress ----

@app.route("/progress")
@login_required
@user_required
def progress():
    exercise_id = request.args.get("exercise_id", type=int)
    series, selected_exercise = [], None
    if exercise_id:
        rows = models.get_progress_series(g.db, session["user_id"], exercise_id)
        series = [{"date": r["date"], "weight_kg": r["top_weight_kg"]} for r in rows]
        selected_exercise = models.get_exercise(g.db, exercise_id)
    return render_template(
        "progress.html",
        exercises=models.get_all_exercise_names(g.db, session["user_id"]),
        series=series,
        selected_exercise=selected_exercise,
        user_name=session.get("user_name"),
    )


if __name__ == "__main__":
    app.run(debug=True)
