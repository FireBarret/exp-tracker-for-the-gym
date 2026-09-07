// Progress chart: a single-series line of top-set weight over time, drawn as
// inline SVG. Hand-rolled rather than pulling a charting library so the page
// costs ~3KB instead of ~200KB and needs no CDN round trip.

(function () {
  "use strict";

  var NS = "http://www.w3.org/2000/svg";
  var COL = { line: "#4f8cff", pr: "#ffb340", grid: "#2a2e37", text: "#8a8f98" };
  var PAD = { top: 16, right: 14, bottom: 28, left: 40 };

  function el(name, attrs) {
    var n = document.createElementNS(NS, name);
    for (var k in attrs) n.setAttribute(k, attrs[k]);
    return n;
  }

  function niceTicks(min, max, count) {
    if (min === max) { min -= 1; max += 1; }
    var raw = (max - min) / count;
    var mag = Math.pow(10, Math.floor(Math.log10(raw)));
    var step = [1, 2, 2.5, 5, 10].map(function (m) { return m * mag; })
                                 .find(function (s) { return s >= raw; }) || mag * 10;
    var start = Math.floor(min / step) * step;
    var ticks = [];
    for (var v = start; v <= max + step * 0.5; v += step) ticks.push(Math.round(v * 100) / 100);
    return ticks;
  }

  function render(host, series) {
    var W = Math.max(host.clientWidth || 320, 260), H = 240;
    var innerW = W - PAD.left - PAD.right, innerH = H - PAD.top - PAD.bottom;

    var values = series.map(function (p) { return p.weight_kg; });
    var ticks = niceTicks(Math.min.apply(null, values), Math.max.apply(null, values), 4);
    var yMin = ticks[0], yMax = ticks[ticks.length - 1];

    var x = function (i) {
      return PAD.left + (series.length === 1 ? innerW / 2 : (i / (series.length - 1)) * innerW);
    };
    var y = function (v) {
      return PAD.top + innerH - ((v - yMin) / (yMax - yMin || 1)) * innerH;
    };

    var svg = el("svg", {
      viewBox: "0 0 " + W + " " + H, width: "100%", height: H,
      role: "img", "aria-label": "Top set weight over time",
    });

    // horizontal gridlines + y labels
    ticks.forEach(function (t) {
      svg.appendChild(el("line", {
        x1: PAD.left, x2: W - PAD.right, y1: y(t), y2: y(t),
        stroke: COL.grid, "stroke-width": 1,
      }));
      var lbl = el("text", {
        x: PAD.left - 6, y: y(t) + 4, fill: COL.text,
        "font-size": 10, "text-anchor": "end",
      });
      lbl.textContent = t;
      svg.appendChild(lbl);
    });

    // Mark each point that was a new best at the time. On an assistance machine
    // a lower number is the stronger effort, so "best so far" is a minimum.
    var assisted = window.PROGRESS_ASSISTED === true;
    var best = assisted ? Infinity : -Infinity;
    var isPr = values.map(function (v) {
      var pr = assisted ? v < best : v > best;
      if (pr) best = v;
      return pr;
    });

    var path = series.map(function (p, i) {
      return (i ? "L" : "M") + x(i) + " " + y(p.weight_kg);
    }).join(" ");

    svg.appendChild(el("path", {
      d: path + " L" + x(series.length - 1) + " " + (PAD.top + innerH) +
         " L" + x(0) + " " + (PAD.top + innerH) + " Z",
      fill: "rgba(79,140,255,0.13)", stroke: "none",
    }));
    svg.appendChild(el("path", {
      d: path, fill: "none", stroke: COL.line,
      "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round",
    }));

    // x labels: first, last, and the middle one if there's room
    var labelIdx = series.length <= 2 ? series.map(function (_, i) { return i; })
                                      : [0, Math.floor((series.length - 1) / 2), series.length - 1];
    labelIdx.forEach(function (i) {
      var t = el("text", {
        x: x(i), y: H - 8, fill: COL.text, "font-size": 10,
        "text-anchor": i === 0 ? "start" : i === series.length - 1 ? "end" : "middle",
      });
      t.textContent = series[i].date.slice(5);   // MM-DD
      svg.appendChild(t);
    });

    var tip = el("text", { x: 0, y: 0, fill: "#eef0f3", "font-size": 11,
                           "font-weight": 700, "text-anchor": "middle", opacity: 0 });
    series.forEach(function (p, i) {
      var c = el("circle", {
        cx: x(i), cy: y(p.weight_kg), r: isPr[i] ? 5 : 3,
        fill: isPr[i] ? COL.pr : COL.line,
      });
      var hit = el("circle", { cx: x(i), cy: y(p.weight_kg), r: 14, fill: "transparent" });
      function show() {
        tip.textContent = p.date + "  ·  " + p.weight_kg + T.kg + (isPr[i] ? "  · " + T.pb : "");
        tip.setAttribute("x", Math.min(Math.max(x(i), 60), W - 60));
        tip.setAttribute("y", Math.max(y(p.weight_kg) - 12, 12));
        tip.setAttribute("opacity", 1);
      }
      hit.addEventListener("mouseenter", show);
      hit.addEventListener("click", show);
      hit.addEventListener("mouseleave", function () { tip.setAttribute("opacity", 0); });
      svg.appendChild(c);
      svg.appendChild(hit);
    });
    svg.appendChild(tip);

    host.innerHTML = "";
    host.appendChild(svg);
  }

  var T = window.I18N || { kg: "kg", pb: "PB", noWeighted: "No weighted sets logged yet." };

  document.addEventListener("DOMContentLoaded", function () {
    var host = document.getElementById("progress-chart");
    var series = window.PROGRESS_SERIES || [];
    if (!host || !series.length) return;
    series = series.filter(function (p) { return p.weight_kg !== null; });
    if (!series.length) {
      host.textContent = T.noWeighted;
      host.className = "muted";
      return;
    }
    render(host, series);
    var t;
    window.addEventListener("resize", function () {
      clearTimeout(t);
      t = setTimeout(function () { render(host, series); }, 150);
    });
  });
})();
