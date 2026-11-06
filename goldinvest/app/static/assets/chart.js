(function () {
  var select = document.getElementById("coin-select");
  var box = document.getElementById("chart-box");
  var title = document.getElementById("chart-title");
  var meta = document.getElementById("chart-meta");
  var tip = document.getElementById("chart-tip");
  if (!select || !box) return;

  var NS = "http://www.w3.org/2000/svg";
  var TZ = "Europe/Warsaw";
  var fmtAxis = new Intl.DateTimeFormat("pl-PL", { timeZone: TZ, day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
  var fmtFull = new Intl.DateTimeFormat("pl-PL", { timeZone: TZ, day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
  var fmtPln = new Intl.NumberFormat("pl-PL", { style: "currency", currency: "PLN" });

  function el(name, attrs, parent) {
    var n = document.createElementNS(NS, name);
    for (var k in attrs) n.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(n);
    return n;
  }
  function niceStep(range, n) {
    var raw = range / n, pow = Math.pow(10, Math.floor(Math.log10(raw))), f = raw / pow;
    return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * pow;
  }
  function message(text, cls) {
    box.innerHTML = '<p class="p-6 ' + (cls || "text-slate-500") + '"></p>';
    box.firstChild.textContent = text;
  }

  function draw(points) {
    box.innerHTML = "";
    if (!points.length) { message("Brak odczytów dla tej monety."); return; }
    var W = Math.max(box.clientWidth, 320), H = 360;
    var m = { l: 76, r: 20, t: 16, b: 56 };
    var pw = W - m.l - m.r, ph = H - m.t - m.b;
    var xs = points.map(function (p) { return Date.parse(p[0]); });
    var ys = points.map(function (p) { return p[1]; });
    var xmin = Math.min.apply(null, xs), xmax = Math.max.apply(null, xs);
    if (xmin === xmax) { xmin -= 3600000; xmax += 3600000; }
    var ymin = Math.min.apply(null, ys), ymax = Math.max.apply(null, ys);
    if (ymin === ymax) { var d0 = Math.max(ymin * 0.01, 1); ymin -= d0; ymax += d0; }
    var step = niceStep(ymax - ymin, 5);
    ymin = Math.floor(ymin / step) * step;
    ymax = Math.ceil(ymax / step) * step;
    function X(t) { return m.l + (t - xmin) / (xmax - xmin) * pw; }
    function Y(v) { return m.t + ph - (v - ymin) / (ymax - ymin) * ph; }

    var svg = el("svg", { width: W, height: H, viewBox: "0 0 " + W + " " + H, role: "img", "aria-label": "Wykres ceny w złotych" }, box);
    for (var v = ymin; v <= ymax + step / 2; v += step) {
      el("line", { x1: m.l, x2: W - m.r, y1: Y(v), y2: Y(v), stroke: "#e2e8f0" }, svg);
      var yt = el("text", { x: m.l - 8, y: Y(v) + 4, "text-anchor": "end", "font-size": 12, fill: "#64748b" }, svg);
      yt.textContent = new Intl.NumberFormat("pl-PL", { maximumFractionDigits: 2 }).format(v);
    }
    var nt = Math.max(2, Math.min(6, Math.floor(pw / 110)));
    for (var i = 0; i <= nt; i++) {
      var t = xmin + (xmax - xmin) * i / nt;
      el("line", { x1: X(t), x2: X(t), y1: m.t, y2: m.t + ph, stroke: "#f1f5f9" }, svg);
      var xt = el("text", { x: X(t), y: m.t + ph + 20, "text-anchor": "middle", "font-size": 12, fill: "#64748b" }, svg);
      xt.textContent = fmtAxis.format(new Date(t));
    }
    el("line", { x1: m.l, x2: m.l, y1: m.t, y2: m.t + ph, stroke: "#94a3b8" }, svg);
    el("line", { x1: m.l, x2: W - m.r, y1: m.t + ph, y2: m.t + ph, stroke: "#94a3b8" }, svg);
    var xl = el("text", { x: m.l + pw / 2, y: H - 8, "text-anchor": "middle", "font-size": 12, fill: "#475569" }, svg);
    xl.textContent = "Data i godzina odczytu (czas polski)";
    var yl = el("text", { x: 14, y: m.t + ph / 2, "text-anchor": "middle", "font-size": 12, fill: "#475569", transform: "rotate(-90 14 " + (m.t + ph / 2) + ")" }, svg);
    yl.textContent = "Cena [zł]";

    var path = points.map(function (p, i) { return (i ? "L" : "M") + X(xs[i]).toFixed(1) + " " + Y(ys[i]).toFixed(1); }).join(" ");
    el("path", { d: path, fill: "none", stroke: "#0f172a", "stroke-width": 2, "stroke-linejoin": "round" }, svg);
    if (points.length <= 150) {
      points.forEach(function (p, i) { el("circle", { cx: X(xs[i]), cy: Y(ys[i]), r: 3, fill: "#0f172a" }, svg); });
    }
    var hl = el("circle", { r: 6, fill: "#2563eb", stroke: "#fff", "stroke-width": 2, visibility: "hidden" }, svg);
    svg.addEventListener("mousemove", function (ev) {
      var r = svg.getBoundingClientRect();
      var mx = (ev.clientX - r.left) * (W / r.width);
      var best = 0, bd = Infinity;
      xs.forEach(function (x, i) { var dd = Math.abs(X(x) - mx); if (dd < bd) { bd = dd; best = i; } });
      hl.setAttribute("cx", X(xs[best])); hl.setAttribute("cy", Y(ys[best])); hl.setAttribute("visibility", "visible");
      tip.textContent = fmtFull.format(new Date(xs[best])) + " — " + fmtPln.format(ys[best]);
      tip.style.visibility = "visible";
    });
    svg.addEventListener("mouseleave", function () { hl.setAttribute("visibility", "hidden"); tip.style.visibility = "hidden"; });
  }

  var current = null;
  function load() {
    if (!select.value) { title.textContent = ""; meta.textContent = ""; message("Brak zapisanych odczytów. Pierwsze pojawią się po pierwszym cyklu."); return; }
    var parts = select.value.split(":");
    message("Ładowanie…");
    fetch("api/historia?waga=" + encodeURIComponent(parts[0]) + "&produkt_id=" + encodeURIComponent(parts[1]))
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (data) {
        current = data.points;
        title.textContent = data.name;
        var n = data.points.length;
        meta.textContent = n + " odczytów" + (n ? " · od " + fmtFull.format(new Date(data.points[0][0])) : "");
        draw(current);
      })
      .catch(function () { message("Nie udało się wczytać danych.", "text-red-700"); });
  }
  try {
    var saved = sessionStorage.getItem("coin-select");
    if (saved && select.querySelector('option[value="' + saved + '"]')) select.value = saved;
  } catch (e) {}
  select.addEventListener("change", function () {
    try { sessionStorage.setItem("coin-select", select.value); } catch (e) {}
    load();
  });
  setInterval(function () { location.reload(); }, 300000);
  var rt;
  window.addEventListener("resize", function () { clearTimeout(rt); rt = setTimeout(function () { if (current) draw(current); }, 150); });
  load();
})();
