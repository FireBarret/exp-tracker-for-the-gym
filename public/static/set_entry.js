// Set entry screen. Two big numbers (weight / reps); tapping one makes it the
// "active" number that the big +/- chips drive. Tapping the already-active
// number lets you type an exact value.

(function () {
  "use strict";

  var E = window.ENTRY;

  // Chip sets differ per field: kg moves in plate-sized jumps, reps in ones.
  var STEPS = {
    weight: [-0.5, 2.5, 5, 10],
    reps: [-1, 1, 2, 5],
  };

  var state = {
    weight: E.usesWeight ? round2(E.startWeight) : null,
    reps: parseInt(E.startReps, 10) || 0,
    active: E.usesWeight ? "weight" : "reps",
  };

  function round2(n) {
    return Math.round(parseFloat(n) * 100) / 100;
  }

  function fmt(n) {
    if (n === null || n === undefined) return "0";
    return String(round2(n));
  }

  function $(sel) { return document.querySelector(sel); }
  function $all(sel) { return Array.from(document.querySelectorAll(sel)); }

  function render() {
    var wd = $('[data-role="weight-display"]');
    if (wd) wd.textContent = fmt(state.weight);
    $('[data-role="reps-display"]').textContent = String(state.reps);

    $all(".hero-field").forEach(function (f) {
      f.classList.toggle("active", f.dataset.field === state.active);
    });

    renderSteppers();

    var summary = E.usesWeight
      ? fmt(state.weight) + "kg × " + state.reps
      : state.reps + " reps";
    $('[data-role="summary"]').textContent = summary;
  }

  function renderSteppers() {
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
  }

  function bump(delta) {
    if (state.active === "weight") {
      state.weight = Math.max(0, round2(state.weight + delta));
    } else {
      state.reps = Math.max(0, state.reps + delta);
    }
    render();
  }

  function promptExact(field) {
    var current = field === "weight" ? fmt(state.weight) : String(state.reps);
    var label = field === "weight" ? "Weight in kg" : "Reps";
    var input = window.prompt(label, current);
    if (input === null) return;
    var n = parseFloat(input);
    if (isNaN(n) || n < 0) return;
    if (field === "weight") state.weight = round2(n);
    else state.reps = Math.round(n);
    render();
  }

  function initHero() {
    $all(".hero-field").forEach(function (f) {
      f.addEventListener("click", function () {
        var field = f.dataset.field;
        if (state.active === field) promptExact(field);
        else state.active = field;
        render();
      });
    });
  }

  // "Previous" / "PB" chips load their numbers into the entry fields.
  function initRecall() {
    $all('[data-role="recall"]').forEach(function (chip) {
      chip.addEventListener("click", function () {
        var w = chip.dataset.weight;
        var r = chip.dataset.reps;
        if (E.usesWeight && w !== "") state.weight = round2(w);
        if (r !== "") state.reps = parseInt(r, 10);
        render();
      });
    });
  }

  function addSetRow(result) {
    var list = $('[data-role="set-list"]');
    var li = document.createElement("li");
    li.dataset.setId = result.set_id;

    var n = document.createElement("span");
    n.className = "set-n";
    n.textContent = "#" + result.set_number;

    var v = document.createElement("span");
    v.className = "set-val";
    v.textContent = result.weight_kg !== null && result.weight_kg !== undefined
      ? fmt(result.weight_kg) + "kg × " + result.reps
      : result.reps + " reps";

    var del = document.createElement("button");
    del.type = "button";
    del.className = "set-del";
    del.textContent = "×";
    del.dataset.setId = result.set_id;
    del.addEventListener("click", function () { deleteSet(result.set_id, li); });

    li.appendChild(n);
    li.appendChild(v);
    li.appendChild(del);
    list.appendChild(li);
    $('[data-role="empty-note"]').hidden = true;
  }

  async function deleteSet(setId, li) {
    var res = await fetch(E.deleteUrlBase + setId + "/delete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
    if (!res.ok) return;
    li.remove();
    renumber();
  }

  function renumber() {
    var rows = $all('[data-role="set-list"] li');
    rows.forEach(function (row, i) {
      row.querySelector(".set-n").textContent = "#" + (i + 1);
    });
    $('[data-role="empty-note"]').hidden = rows.length > 0;
  }

  function initExistingDeletes() {
    $all('[data-role="delete-set"]').forEach(function (btn) {
      btn.addEventListener("click", function () {
        deleteSet(btn.dataset.setId, btn.closest("li"));
      });
    });
  }

  function initAddSet() {
    var btn = $('[data-role="add-set"]');
    btn.addEventListener("click", async function () {
      if (state.reps <= 0) return;
      btn.disabled = true;
      try {
        var res = await fetch(E.logUrl, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            exercise_id: E.exerciseId,
            weight_kg: E.usesWeight ? state.weight : null,
            reps: state.reps,
          }),
        });
        if (!res.ok) {
          var err = await res.json().catch(function () { return {}; });
          alert(err.error || "Failed to add set");
          return;
        }
        addSetRow(await res.json());
        btn.classList.add("flash");
        setTimeout(function () { btn.classList.remove("flash"); }, 400);
      } finally {
        btn.disabled = false;
      }
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    initHero();
    initRecall();
    initAddSet();
    initExistingDeletes();
    render();
  });
})();
