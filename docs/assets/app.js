(function () {
  var root = document.documentElement;

  // Theme toggle (preference is a per-browser convenience; works without storage)
  document.getElementById("theme").onclick = function () {
    var dark = root.dataset.theme === "dark" ||
      (!root.dataset.theme && matchMedia("(prefers-color-scheme: dark)").matches);
    var next = dark ? "light" : "dark";
    root.dataset.theme = next;
    try { localStorage.setItem("vigil-theme", next); } catch (e) {}
  };

  // Mobile menu
  var side = document.getElementById("side");
  document.getElementById("menu").onclick = function () { side.classList.toggle("open"); };

  // Copy buttons
  document.querySelectorAll(".code .copy").forEach(function (b) {
    b.onclick = function () {
      var text = b.parentNode.querySelector("code").innerText;
      var done = function (msg) { b.textContent = msg; setTimeout(function () { b.textContent = "Copy"; }, 1500); };
      if (navigator.clipboard) navigator.clipboard.writeText(text).then(function () { done("Copied"); }, function () { done("Failed"); });
      else done("Press Ctrl+C");
    };
  });

  // Search over the prebuilt index (assets/search-index.js)
  var q = document.getElementById("q"), box = document.getElementById("results");
  var base = document.body.dataset.base || "", idx = window.VIGIL_INDEX || [];
  var esc = function (s) { return s.replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); };

  function run() {
    var terms = q.value.toLowerCase().split(/\s+/).filter(Boolean);
    if (!terms.length) { box.hidden = true; return; }
    var hits = [];
    idx.forEach(function (p) {
      var title = p.t.toLowerCase(), heads = p.h.join(" ").toLowerCase(), text = p.x.toLowerCase(), score = 0;
      for (var i = 0; i < terms.length; i++) {
        var s = 0;
        if (title.indexOf(terms[i]) > -1) s += 10;
        if (heads.indexOf(terms[i]) > -1) s += 5;
        if (text.indexOf(terms[i]) > -1) s += 1;
        if (!s) { score = 0; break; }
        score += s;
      }
      if (score) {
        var at = text.indexOf(terms[0]);
        hits.push({ p: p, score: score, snip: at > -1 ? p.x.substr(Math.max(0, at - 40), 120) : p.s });
      }
    });
    hits.sort(function (a, b) { return b.score - a.score; });
    box.innerHTML = hits.length
      ? hits.slice(0, 8).map(function (h) {
          return '<a href="' + base + h.p.u + '"><b>' + esc(h.p.t) + "</b><small>…" + esc(h.snip) + "…</small></a>";
        }).join("")
      : "<a><small>No matches. Try another word, such as token or chain.</small></a>";
    box.hidden = false;
  }

  q.addEventListener("input", run);
  q.addEventListener("keydown", function (e) { if (e.key === "Escape") { box.hidden = true; q.blur(); } });
  document.addEventListener("keydown", function (e) {
    if (e.key === "/" && !/input|textarea/i.test(document.activeElement.tagName)) { e.preventDefault(); q.focus(); }
  });
  document.addEventListener("click", function (e) { if (!box.contains(e.target) && e.target !== q) box.hidden = true; });
})();
