// Tap-to-log UI: Repeat / +step buttons do the logging in one tap using whatever
// is in the reps field. Custom weight is a secondary, smaller path.

(function () {
  "use strict";

  function $all(sel, root) {
    return Array.from((root || document).querySelectorAll(sel));
  }

  async function postSet(exerciseId, weightKg, reps) {
    const res = await fetch(window.LOG_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ exercise_id: exerciseId, weight_kg: weightKg, reps: reps }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.error || "Failed to log set");
    }
    return res.json();
  }

  function flash(button) {
    button.classList.add("logged");
    setTimeout(() => button.classList.remove("logged"), 500);
  }

  function updateCard(card, result) {
    const setCountEl = card.querySelector('[data-role="set-count"]');
    const targetSets = result.target_sets;
    if (setCountEl) {
      setCountEl.textContent = targetSets ? `${result.set_count}/${targetSets} sets` : `${result.set_count} sets`;
      if (targetSets && result.set_count >= targetSets) {
        setCountEl.classList.add("complete");
      }
    }

    const log = card.querySelector('[data-role="set-log"]');
    if (log) {
      const li = document.createElement("li");
      const weightLabel = result.weight_kg !== null && result.weight_kg !== undefined ? `${result.weight_kg}kg` : "BW";
      li.textContent = `#${result.set_number}: ${weightLabel} × ${result.reps}`;
      log.appendChild(li);
    }

    // Keep repeat/+step buttons in sync with the latest logged weight, so the
    // next tap on this exercise (later in the same session) uses fresh numbers.
    if (result.weight_kg !== null && result.weight_kg !== undefined) {
      const repeatBtn = card.querySelector('[data-role="repeat"]');
      const stepBtn = card.querySelector('[data-role="step"]');
      if (repeatBtn) {
        repeatBtn.dataset.weight = result.next_repeat_weight;
        repeatBtn.innerHTML = `Repeat<br><b>${result.next_repeat_weight}kg</b>`;
      }
      if (stepBtn && result.next_step_weight !== null && result.next_step_weight !== undefined) {
        stepBtn.dataset.weight = result.next_step_weight;
        stepBtn.innerHTML = `+${card.dataset.stepKg}<br><b>${result.next_step_weight}kg</b>`;
      }
    }
  }

  function getReps(card) {
    const repsInput = card.querySelector('[data-role="reps"]');
    const val = repsInput ? repsInput.value.trim() : "";
    if (val === "") {
      repsInput && repsInput.focus();
      return null;
    }
    const n = parseInt(val, 10);
    if (isNaN(n) || n < 0) {
      repsInput && repsInput.focus();
      return null;
    }
    return n;
  }

  function initExerciseCards() {
    $all(".exercise-card").forEach((card) => {
      const exerciseId = parseInt(card.dataset.exerciseId, 10);

      $all('[data-role="repeat"], [data-role="step"], [data-role="bodyweight"]', card).forEach((btn) => {
        btn.addEventListener("click", async () => {
          const reps = getReps(card);
          if (reps === null) return;
          const weightAttr = btn.dataset.weight;
          const weightKg = weightAttr === undefined || weightAttr === "" ? null : parseFloat(weightAttr);
          btn.disabled = true;
          try {
            const result = await postSet(exerciseId, weightKg, reps);
            flash(btn);
            updateCard(card, result);
          } catch (err) {
            alert(err.message);
          } finally {
            btn.disabled = false;
          }
        });
      });

      const customBtn = card.querySelector('[data-role="custom-log"]');
      if (customBtn) {
        customBtn.addEventListener("click", async () => {
          const reps = getReps(card);
          if (reps === null) return;
          const customInput = card.querySelector('[data-role="custom-weight"]');
          const raw = customInput ? customInput.value.trim() : "";
          const weightKg = raw === "" ? null : parseFloat(raw);
          customBtn.disabled = true;
          try {
            const result = await postSet(exerciseId, weightKg, reps);
            flash(customBtn);
            updateCard(card, result);
            if (customInput) customInput.value = "";
          } catch (err) {
            alert(err.message);
          } finally {
            customBtn.disabled = false;
          }
        });
      }
    });
  }

  function initNotes() {
    const saveBtn = document.getElementById("save-notes");
    if (!saveBtn) return;
    saveBtn.addEventListener("click", async () => {
      const notes = document.getElementById("session-notes").value;
      const res = await fetch(window.NOTES_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ notes }),
      });
      if (res.ok) {
        const saved = document.getElementById("notes-saved");
        saved.hidden = false;
        setTimeout(() => (saved.hidden = true), 1500);
      }
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    initExerciseCards();
    initNotes();
  });
})();
