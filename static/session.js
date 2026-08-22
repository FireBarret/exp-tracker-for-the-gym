// Session plan page: just the notes box (everything else is plain links/forms).
(function () {
  "use strict";
  document.addEventListener("DOMContentLoaded", function () {
    var saveBtn = document.getElementById("save-notes");
    if (!saveBtn) return;
    saveBtn.addEventListener("click", async function () {
      var notes = document.getElementById("session-notes").value;
      var res = await fetch(window.NOTES_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ notes: notes }),
      });
      if (res.ok) {
        var saved = document.getElementById("notes-saved");
        saved.hidden = false;
        setTimeout(function () { saved.hidden = true; }, 1500);
      }
    });
  });
})();
