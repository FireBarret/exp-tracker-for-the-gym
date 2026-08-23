import csv
import io
import os
from datetime import date
from functools import wraps

from flask import (Flask, Response, abort, g, jsonify, redirect,
                   render_template, request, session, url_for)

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
    exercises = models.get_session_exercises(g.db, session_id)

    grouped = {}
    for ex in exercises:
        grouped.setdefault(ex["muscle_group"], []).append(ex)

    return render_template(
        "session.html",
        session_row=sess,
        split=split,
        grouped=grouped,
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
