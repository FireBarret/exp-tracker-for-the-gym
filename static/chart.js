// Renders the progress line chart (top set weight per session) with PR points highlighted.

(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", () => {
    const canvas = document.getElementById("progress-chart");
    if (!canvas) return;

    const series = window.PROGRESS_SERIES || [];
    const labels = series.map((p) => p.date);
    const values = series.map((p) => p.weight_kg);

    // Mark a point as a PR if it's a new max-so-far.
    let maxSoFar = -Infinity;
    const pointColors = values.map((v) => {
      const isPr = v !== null && v > maxSoFar;
      if (v !== null && v > maxSoFar) maxSoFar = v;
      return isPr ? "#3ecf8e" : "#4f8cff";
    });
    const pointRadii = values.map((v, i) => (pointColors[i] === "#3ecf8e" ? 6 : 3));

    new Chart(canvas.getContext("2d"), {
      type: "line",
      data: {
        labels: labels,
        datasets: [
          {
            label: window.PROGRESS_EXERCISE_NAME + " — top set (kg)",
            data: values,
            borderColor: "#4f8cff",
            backgroundColor: "rgba(79, 140, 255, 0.15)",
            pointBackgroundColor: pointColors,
            pointBorderColor: pointColors,
            pointRadius: pointRadii,
            tension: 0.2,
            fill: true,
            spanGaps: true,
          },
        ],
      },
      options: {
        responsive: true,
        plugins: {
          legend: { labels: { color: "#eef0f3" } },
          tooltip: {
            callbacks: {
              label: (ctx) => `${ctx.parsed.y}kg${pointColors[ctx.dataIndex] === "#3ecf8e" ? " — PR" : ""}`,
            },
          },
        },
        scales: {
          x: { ticks: { color: "#8a8f98" }, grid: { color: "#2a2e37" } },
          y: { ticks: { color: "#8a8f98" }, grid: { color: "#2a2e37" } },
        },
      },
    });
  });
})();
