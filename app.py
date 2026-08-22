import os
from datetime import date
from functools import wraps

from flask import Flask, abort, g, jsonify, redirect, render_template, request, session, url_for

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import models

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-me")

APP_PASSWORD = os.environ.get("GYM_APP_PASSWORD")


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


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        # If no password is configured, don't lock the owner out -- treat as open (dev mode).
        if not APP_PASSWORD or request.form.get("password") == APP_PASSWORD:
            session["authed"] = True
            next_url = request.args.get("next") or url_for("home")
            return redirect(next_url)
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
    users = models.get_users(g.db)
    return render_template("home.html", users=users)


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
    all_splits = models.get_splits(g.db)
    return render_template("home.html", splits=all_splits, user_name=session.get("user_name"))


@app.route("/session/start", methods=["POST"])
@login_required
@user_required
def start_session():
    split_id = request.form.get("split_id", type=int)
    if not split_id:
        abort(400)
    session_id = models.create_session(
        g.db, session["user_id"], split_id, date.today().isoformat()
    )
    return redirect(url_for("session_log", session_id=session_id))


# ---- logging ----

@app.route("/session/<int:session_id>")
@login_required
@user_required
def session_log(session_id):
    sess = models.get_session(g.db, session_id)
    if not sess or sess["user_id"] != session["user_id"]:
        abort(404)
    split = models.get_split(g.db, sess["split_id"])
    exercises = models.get_exercises_for_split(g.db, sess["split_id"])

    grouped = {}
    for ex in exercises:
        last_set = models.get_last_set_for_exercise(g.db, session["user_id"], ex["id"])
        set_count = models.get_set_count_for_exercise(g.db, session_id, ex["id"])
        last_weight = last_set["weight_kg"] if last_set else None
        step = ex["step_kg"]
        entry = {
            "id": ex["id"],
            "name": ex["name"],
            "target_sets": ex["target_sets"],
            "target_rep_range": ex["target_rep_range"],
            "step_kg": step,
            "last_weight_kg": last_weight,
            "last_reps": last_set["reps"] if last_set else None,
            "repeat_weight": last_weight,
            "step_weight": (last_weight + step) if last_weight is not None else None,
            "set_count": set_count,
        }
        grouped.setdefault(ex["muscle_group"], []).append(entry)

    return render_template(
        "log.html",
        session_row=sess,
        split=split,
        grouped=grouped,
        user_name=session.get("user_name"),
    )


@app.route("/session/<int:session_id>/log", methods=["POST"])
@login_required
@user_required
def log_set(session_id):
    sess = models.get_session(g.db, session_id)
    if not sess or sess["user_id"] != session["user_id"]:
        abort(404)

    data = request.get_json(silent=True) or request.form
    # request.get_json returns a plain dict (no `.get(..., type=)`); request.form supports it.
    if isinstance(data, dict):
        exercise_id = data.get("exercise_id")
        weight_kg = data.get("weight_kg")
        reps = data.get("reps")
    else:
        exercise_id = data.get("exercise_id", type=int)
        weight_kg = data.get("weight_kg", type=float)
        reps = data.get("reps", type=int)

    if not exercise_id or reps is None:
        return jsonify({"error": "exercise_id and reps are required"}), 400

    exercise_id = int(exercise_id)
    reps = int(reps)
    weight_kg = float(weight_kg) if weight_kg not in (None, "", "null") else None

    set_id, set_number = models.log_set(g.db, session_id, exercise_id, weight_kg, reps)
    set_count = models.get_set_count_for_exercise(g.db, session_id, exercise_id)
    exercise = models.get_exercise(g.db, exercise_id)

    return jsonify({
        "ok": True,
        "set_id": set_id,
        "set_number": set_number,
        "set_count": set_count,
        "target_sets": exercise["target_sets"],
        "weight_kg": weight_kg,
        "reps": reps,
        "next_repeat_weight": weight_kg,
        "next_step_weight": (weight_kg + exercise["step_kg"]) if weight_kg is not None else None,
    })


@app.route("/session/<int:session_id>/notes", methods=["POST"])
@login_required
@user_required
def session_notes(session_id):
    sess = models.get_session(g.db, session_id)
    if not sess or sess["user_id"] != session["user_id"]:
        abort(404)
    notes = (request.get_json(silent=True) or {}).get("notes", "") if request.is_json else request.form.get("notes", "")
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
    sessions_with_sets = []
    for s in sessions:
        sets = models.get_sets_for_session(g.db, s["id"])
        sessions_with_sets.append({"session": s, "sets": sets})
    all_splits = models.get_splits(g.db)
    all_exercises = models.get_all_exercise_names(g.db, session["user_id"])
    return render_template(
        "history.html",
        sessions_with_sets=sessions_with_sets,
        all_splits=all_splits,
        all_exercises=all_exercises,
        selected_split_id=split_id,
        selected_exercise_id=exercise_id,
        user_name=session.get("user_name"),
    )


# ---- progress ----

@app.route("/progress")
@login_required
@user_required
def progress():
    exercise_id = request.args.get("exercise_id", type=int)
    exercises = models.get_all_exercise_names(g.db, session["user_id"])
    series = []
    selected_exercise = None
    if exercise_id:
        rows = models.get_progress_series(g.db, session["user_id"], exercise_id)
        series = [{"date": r["date"], "weight_kg": r["top_weight_kg"]} for r in rows]
        selected_exercise = models.get_exercise(g.db, exercise_id)
    return render_template(
        "progress.html",
        exercises=exercises,
        series=series,
        selected_exercise=selected_exercise,
        user_name=session.get("user_name"),
    )


if __name__ == "__main__":
    app.run(debug=True)
