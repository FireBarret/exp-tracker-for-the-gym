// Session screen. The plan list and the set-entry screen live on one page: all
// the data for every exercise arrives with the initial load, so switching
// between them costs no network request. Only writes (logging or deleting a
// set) talk to the server.

(function () {
  "use strict";

  var S = window.SESSION;
  var DATA = JSON.parse(document.getElementById("session-data").textContent);
  var BY_ID = {};
  DATA.forEach(function (ex) { BY_ID[ex.id] = ex; });

  var T = window.I18N || {};
  var STEPS = { weight: [-0.5, 2.5, 5, 10], reps: [-1, 1, 2, 5] };

  var planView = document.getElementById("plan-view");
  var entryView = document.getElementById("entry-view");
  var current = null;                 // exercise currently open
  var state = { weight: 0, reps: 0, active: "weight" };

  function $(sel, root) { return (root || document).querySelector(sel); }
  function $all(sel, root) { return Array.from((root || document).querySelectorAll(sel)); }
  function round2(n) { return Math.round(parseFloat(n) * 100) / 100; }
  function fmt(n) { return n === null || n === undefined ? "0" : String(round2(n)); }

  function describe(entry) {
    if (!entry) return "—";
    return (entry.weight !== null && entry.weight !== undefined
      ? fmt(entry.weight) + T.kg + " × " : "") + entry.reps;
  }

  // ---- opening / closing the entry screen ----

  function openExercise(id, push) {
    current = BY_ID[id];
    if (!current) return;

    $('[data-role="ex-name"]').textContent = current.name;
    $('[data-role="ex-target"]').textContent =
      (current.target_sets || "") + "×" + (current.target_reps || "");

    var prevChip = $('[data-role="recall-prev"]');
    var pbChip = $('[data-role="recall-pb"]');
    $('[data-role="prev-value"]').textContent = describe(current.previous);
    $('[data-role="pb-value"]').textContent = describe(current.pb);
    prevChip.classList.toggle("empty", !current.previous);
    pbChip.classList.toggle("empty", !current.pb);
    prevChip.disabled = !current.previous;
    pbChip.disabled = !current.pb;

    // Assistance machines run the other way: less weight is the harder set, so
    // the field is labelled differently and the screen says so.
    var assisted = current.weight_mode === "assisted";
    var weightField = $('.hero-field[data-field="weight"]');
    weightField.hidden = !current.uses_weight;
    $('[data-role="weight-label"]').textContent = assisted ? T.assist : T.weight;
    $('[data-role="assist-note"]').hidden = !assisted;

    // Start from the last set done here, else last workout, else a default.
    var last = current.sets.length ? current.sets[current.sets.length - 1] : null;
    var seed = last || current.previous;
    state.weight = current.uses_weight ? round2(seed && seed.weight != null ? seed.weight : 20) : null;
    state.reps = seed ? seed.reps : 10;
    state.active = current.uses_weight ? "weight" : "reps";

    renderSets();
    render();

    planView.hidden = true;
    entryView.hidden = false;
    window.scrollTo(0, 0);
    if (push) history.pushState({ exerciseId: id }, "", S.entryBase + id);
  }

  function closeEntry(push) {
    entryView.hidden = true;
    planView.hidden = false;
    current = null;
    window.scrollTo(0, 0);
    if (push) history.pushState({}, "", "/session/" + S.id);
  }

  // ---- rendering the entry screen ----

  function render() {
    if (!current) return;
    if (current.uses_weight) $('[data-role="weight-display"]').textContent = fmt(state.weight);
    $('[data-role="reps-display"]').textContent = String(state.reps);

    $all(".hero-field").forEach(function (f) {
      f.classList.toggle("active", f.dataset.field === state.active);
    });

    var wrap = $('[data-role="steppers"]');
    wrap.innerHTML = "";
    STEPS[state.active].forEach(function (delta) {
      var b = document.createElement("button");
      b.type = "button";
      b.className = "step-btn" + (delta < 0 ? " minus" : "");
      b.textContent = (delta > 0 ? "+" : "−") + Math.abs(delta);
      b.addEventListener("click", function () { bump(delta); });
      wrap.appendChild(b);
    });

    $('[data-role="summary"]').textContent = current.uses_weight
      ? fmt(state.weight) + T.kg + " × " + state.reps
      : state.reps + " " + T.reps;
  }

  function renderSets() {
    var list = $('[data-role="set-list"]');
    list.innerHTML = "";
    current.sets.forEach(function (st, i) {
      var li = document.createElement("li");

      var n = document.createElement("span");
      n.className = "set-n";
      n.textContent = "#" + (i + 1);

      var v = document.createElement("span");
      v.className = "set-val";
      v.textContent = st.weight !== null && st.weight !== undefined
        ? fmt(st.weight) + T.kg + " × " + st.reps
        : st.reps + " " + T.reps;

      var del = document.createElement("button");
      del.type = "button";
      del.className = "set-del";
      del.textContent = "×";
      del.addEventListener("click", function () { deleteSet(st.id); });

      li.appendChild(n); li.appendChild(v); li.appendChild(del);
      list.appendChild(li);
    });
    $('[data-role="empty-note"]').hidden = current.sets.length > 0;
  }

  function updatePlanRow(ex) {
    var badge = document.querySelector('[data-count-for="' + ex.id + '"]');
    if (badge) {
      badge.textContent = ex.sets.length + (ex.target_sets ? "/" + ex.target_sets : "");
    }
    var row = document.querySelector('[data-row-for="' + ex.id + '"]');
    if (row) {
      row.classList.toggle("done", !!ex.target_sets && ex.sets.length >= ex.target_sets);
    }
  }

  function bump(delta) {
    if (state.active === "weight") state.weight = Math.max(0, round2(state.weight + delta));
    else state.reps = Math.max(0, state.reps + delta);
    render();
  }

  function promptExact(field) {
    var cur = field === "weight" ? fmt(state.weight) : String(state.reps);
    var input = window.prompt(field === "weight" ? T.promptWeight : T.promptReps, cur);
    if (input === null) return;
    var n = parseFloat(input);
    if (isNaN(n) || n < 0) return;
    if (field === "weight") state.weight = round2(n); else state.reps = Math.round(n);
    render();
  }

  // ---- writes (the only things that hit the server) ----

  async function addSet() {
    if (!current || state.reps <= 0) return;
    var btn = $('[data-role="add-set"]');
    btn.disabled = true;
    try {
      var res = await fetch(S.logUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          exercise_id: current.id,
          weight_kg: current.uses_weight ? state.weight : null,
          reps: state.reps,
        }),
      });
      if (!res.ok) {
        var err = await res.json().catch(function () { return {}; });
        alert(err.error || T.saveFailed);
        return;
      }
      var r = await res.json();
      current.sets.push({ id: r.set_id, n: r.set_number, weight: r.weight_kg, reps: r.reps });
      renderSets();
      updatePlanRow(current);
      btn.classList.add("flash");
      setTimeout(function () { btn.classList.remove("flash"); }, 400);
    } catch (e) {
      alert(T.saveFailed);
    } finally {
      btn.disabled = false;
    }
  }

  async function deleteSet(setId) {
    try {
      var res = await fetch(S.deleteBase + setId + "/delete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: "{}",
      });
      if (!res.ok) return;
      current.sets = current.sets.filter(function (s) { return s.id !== setId; });
      renderSets();
      updatePlanRow(current);
    } catch (e) { /* leave the row alone if the delete didn't land */ }
  }

  // ---- wiring ----

  function init() {
    $all("[data-open-exercise]").forEach(function (a) {
      a.addEventListener("click", function (e) {
        e.preventDefault();
        openExercise(parseInt(a.dataset.openExercise, 10), true);
      });
    });

    $('[data-role="close-entry"]').addEventListener("click", function () { closeEntry(true); });

    $all(".hero-field").forEach(function (f) {
      f.addEventListener("click", function () {
        if (state.active === f.dataset.field) promptExact(f.dataset.field);
        else state.active = f.dataset.field;
        render();
      });
    });

    $('[data-role="recall-prev"]').addEventListener("click", function () {
      if (!current || !current.previous) return;
      if (current.uses_weight && current.previous.weight != null) state.weight = round2(current.previous.weight);
      state.reps = current.previous.reps;
      render();
    });
    $('[data-role="recall-pb"]').addEventListener("click", function () {
      if (!current || !current.pb) return;
      if (current.uses_weight && current.pb.weight != null) state.weight = round2(current.pb.weight);
      state.reps = current.pb.reps;
      render();
    });

    $('[data-role="add-set"]').addEventListener("click", addSet);

    // Browser back closes the entry screen instead of leaving the page.
    window.addEventListener("popstate", function (e) {
      if (e.state && e.state.exerciseId) openExercise(e.state.exerciseId, false);
      else closeEntry(false);
    });

    // Deep link straight to an exercise (refresh, or a link from elsewhere).
    var m = location.pathname.match(/\/exercise\/(\d+)$/);
    if (m && BY_ID[m[1]]) openExercise(parseInt(m[1], 10), false);

    var saveBtn = document.getElementById("save-notes");
    if (saveBtn) {
      saveBtn.addEventListener("click", async function () {
        var res = await fetch(S.notesUrl, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ notes: document.getElementById("session-notes").value }),
        });
        if (res.ok) {
          var saved = document.getElementById("notes-saved");
          saved.hidden = false;
          setTimeout(function () { saved.hidden = true; }, 1500);
        }
      });
    }
  }

  document.addEventListener("DOMContentLoaded", init);
})();
