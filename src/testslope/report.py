"""Render a catalogue as one self-contained HTML file: summary tiles, filters, a table with a code preview on hover, and a detail view.

The page has no external requests. All data is inserted with ``textContent`` (never ``innerHTML``) because test code and docstrings are
untrusted text from the point of view of a web page. The catalogue is embedded as JSON with ``<`` escaped so it cannot close the script tag.
"""
from __future__ import annotations

import json
import re
from typing import Any

from .scanner import FLAG_HELP, RISK_FLAGS

TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>testslope: __PROJECT__</title>
<style>
:root { --bg:#f4f6f9; --panel:#fff; --fg:#1b2230; --muted:#5a6578; --line:#d8deea; --accent:#1f5fd1; --ok:#146c36; --warn:#9a5b00; --bad:#b3261e;
        --chip:#e8edf5; --chip-ok:#dff3e6; --chip-warn:#fbebd2; --chip-bad:#fbe3e0; --code:#f0f3f9; --mono:ui-monospace,SFMono-Regular,Consolas,monospace; }
@media (prefers-color-scheme: dark) { :root { --bg:#12161d; --panel:#1b212b; --fg:#e5e9f0; --muted:#a0a9b8; --line:#2b3340; --accent:#6ea3ff; --ok:#5fd08a; --warn:#f0b756;
        --bad:#ff8077; --chip:#262d38; --chip-ok:#1b3a29; --chip-warn:#3d2f14; --chip-bad:#432220; --code:#171c24; } }
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--fg); font:15px/1.45 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif; }
header, main { max-width:1200px; margin:0 auto; padding:16px; }
h1 { margin:0 0 4px; font-size:22px; } h2 { font-size:17px; margin:20px 0 8px; }
.muted { color:var(--muted); }
.tiles { display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:12px; margin:12px 0; }
.tile { background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:10px 12px; }
.tile b { display:block; font-size:24px; } .tile.warn b { color:var(--warn); } .tile.bad b { color:var(--bad); } .tile.ok b { color:var(--ok); }
.form { display:flex; flex-wrap:wrap; gap:10px; align-items:end; margin:12px 0; }
label { display:flex; flex-direction:column; font-size:13px; color:var(--muted); gap:3px; } label.inline { flex-direction:row; align-items:center; gap:6px; }
input[type=text], select { font:inherit; padding:6px 8px; border:1px solid var(--line); border-radius:6px; background:var(--panel); color:var(--fg); }
button { font:inherit; padding:6px 12px; border:1px solid var(--accent); border-radius:6px; background:var(--accent); color:#fff; cursor:pointer; }
button.secondary { background:transparent; color:var(--accent); }
.scroll { overflow-x:auto; background:var(--panel); border:1px solid var(--line); border-radius:8px; }
table { border-collapse:collapse; width:100%; } th, td { padding:7px 10px; text-align:left; border-bottom:1px solid var(--line); vertical-align:top; }
th { font-size:12px; text-transform:uppercase; letter-spacing:.03em; color:var(--muted); background:var(--code); } td.num { text-align:right; }
.chip { display:inline-block; padding:1px 8px; margin:1px 3px 1px 0; border-radius:10px; font-size:12px; background:var(--chip); }
.chip.ok { background:var(--chip-ok); color:var(--ok); } .chip.warn { background:var(--chip-warn); color:var(--warn); } .chip.bad { background:var(--chip-bad); color:var(--bad); }
code, pre { font-family:var(--mono); font-size:12.5px; } pre { background:var(--code); border:1px solid var(--line); border-radius:6px; padding:10px; overflow:auto; max-height:70vh; }
.nr { cursor:help; font-weight:600; border-bottom:1px dotted currentColor; }
.nr .tip { display:none; position:fixed; z-index:20; max-width:min(640px,92vw); max-height:45vh; overflow:hidden; margin-top:6px; padding:10px 12px; font:12px/1.4 var(--mono);
           font-weight:400; text-align:left; white-space:pre; background:var(--panel); color:var(--fg); border:1px solid var(--line); border-radius:6px; box-shadow:0 4px 14px rgba(0,0,0,.25); }
.nr:hover .tip, .nr:focus .tip { display:block; }
details { margin:8px 0; } summary { cursor:pointer; font-weight:600; }
</style>
</head>
<body>
<header>
  <h1 id="title"></h1>
  <div class="muted" id="sub"></div>
  <div class="tiles" id="tiles"></div>
  <div class="form">
    <label>Search <input id="q" type="text" placeholder="name or description" maxlength="80" autocomplete="off"></label>
    <label>Flag <select id="flag"><option value="">any</option></select></label>
    <label>Module <select id="module"><option value="">any</option></select></label>
    <label class="inline"><input id="unlisted" type="checkbox"> not in runner</label>
    <label class="inline"><input id="failing" type="checkbox"> failing</label>
  </div>
</header>
<main>
  <h2>Tests <span class="muted">(numbered in order of creation; hover a number for the first lines of code)</span></h2>
  <div class="scroll"><table id="table"></table></div>
  <div id="detail"></div>
</main>
<script id="data" type="application/json">__DATA__</script>
<script>
(function () {
  "use strict";
  var DATA = JSON.parse(document.getElementById("data").textContent);
  var FLAG_HELP = __FLAG_HELP__, RISK = new Set(__RISK__);
  var tests = DATA.tests;
  function el(tag, attrs, kids) {
    var e = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) { if (k === "text") e.textContent = attrs[k]; else if (k === "onclick") e.addEventListener("click", attrs[k]); else e.setAttribute(k, attrs[k]); });
    (kids || []).forEach(function (c) { e.appendChild(typeof c === "string" ? document.createTextNode(c) : c); });
    return e;
  }
  function chip(text, kind, title) { return el("span", { "class": "chip" + (kind ? " " + kind : ""), text: text, title: title || "" }); }
  function day(d) { return d ? String(d).slice(0, 10) : "-"; }
  function flags(list) { return el("span", {}, (list || []).map(function (f) { return chip(f, RISK.has(f) ? "warn" : "", FLAG_HELP[f] || f); })); }
  function result(t) {
    if (t.last_rc === null || t.last_rc === undefined) return el("span", { "class": "muted", text: "n/a" });
    return chip(t.last_rc === 0 ? "pass" : "fail", t.last_rc === 0 ? "ok" : "bad");
  }
  function runner(t) {
    if (t.in_runner === null || t.in_runner === undefined) return el("span", { "class": "muted", text: "n/a" });
    return t.in_runner ? chip("yes", "ok") : chip("no", "bad", "no runner script mentions this file, so nothing guarantees it runs");
  }
  function nr(t) { return el("span", { "class": "nr", tabindex: "0" }, ["#" + t.num, el("span", { "class": "tip", text: t.preview || "(no preview)" })]); }
  function tile(label, value, kind, note) { return el("div", { "class": "tile" + (kind ? " " + kind : "") }, [el("span", { "class": "muted", text: label }), el("b", { text: String(value) }), el("span", { "class": "muted", text: note || "" })]); }
  function count(list, key) { var m = {}; list.forEach(function (t) { (t[key] || []).forEach(function (v) { m[v] = (m[v] || 0) + 1; }); }); return m; }

  function summary() {
    var risky = tests.filter(function (t) { return (t.flags || []).some(function (f) { return RISK.has(f); }); }).length;
    var unlisted = tests.filter(function (t) { return t.in_runner === false; }).length;
    var known = tests.some(function (t) { return t.in_runner !== null && t.in_runner !== undefined; });
    var withRes = tests.filter(function (t) { return t.last_rc !== null && t.last_rc !== undefined; });
    var failing = withRes.filter(function (t) { return t.last_rc !== 0; }).length;
    var secs = withRes.reduce(function (a, t) { return a + (t.last_seconds || 0); }, 0);
    var tiles = document.getElementById("tiles");
    tiles.appendChild(tile("Tests", tests.length, "", tests.reduce(function (a, t) { return a + t.lines; }, 0) + " lines, " + tests.reduce(function (a, t) { return a + t.asserts; }, 0) + " asserts"));
    tiles.appendChild(tile("Risky patterns", risky, risky ? "warn" : "ok", "sleep, unseeded randomness, wall clock"));
    tiles.appendChild(tile("Not in runner", known ? unlisted : "n/a", unlisted ? "bad" : "", known ? "never mentioned by " + DATA.runner_files.join(", ") : "pass --runner to check"));
    tiles.appendChild(tile("Last run", withRes.length ? (withRes.length - failing) + "/" + withRes.length : "n/a", failing ? "bad" : "", withRes.length ? Math.round(secs) + " s in total" : "pass --junit to attach results"));
    document.getElementById("title").textContent = "testslope: " + DATA.project;
    document.getElementById("sub").textContent = "Scanned " + String(DATA.generated_at).replace("T", " ").slice(0, 16) + " UTC. Nothing was executed; all fields come from reading files and git history.";
    var f = document.getElementById("flag"), m = document.getElementById("module");
    var fc = count(tests, "flags"), mc = count(tests, "modules");
    Object.keys(fc).sort().forEach(function (k) { f.appendChild(el("option", { value: k, text: k + " (" + fc[k] + ")" })); });
    Object.keys(mc).sort().forEach(function (k) { m.appendChild(el("option", { value: k, text: k + " (" + mc[k] + ")" })); });
  }

  function open(t) {
    var box = document.getElementById("detail");
    while (box.firstChild) box.removeChild(box.firstChild);
    box.appendChild(el("h2", { text: "#" + t.num + " " + t.name }));
    box.appendChild(el("p", {}, [el("code", { text: t.path }), " ", flags(t.flags), " runner: ", runner(t), " last run: ", result(t),
                                 t.last_seconds !== null && t.last_seconds !== undefined ? el("span", { "class": "muted", text: " " + t.last_seconds + " s" }) : ""]));
    box.appendChild(el("ul", {}, [
      el("li", { text: "First commit: " + day(t.first_commit) + ", last: " + day(t.last_commit) + ", commits: " + t.commits }),
      el("li", { text: t.lines + " lines, " + t.asserts + " asserts, " + (t.functions || []).length + " test functions" }),
      el("li", {}, ["Touches modules: ", (t.modules || []).length ? (t.modules || []).map(function (x) { return el("code", { text: x + " " }); }) : "-"]),
    ]));
    if (t.doc) box.appendChild(el("details", { open: "" }, [el("summary", { text: "Description (module docstring)" }), el("pre", { text: t.doc })]));
    if ((t.functions || []).length) box.appendChild(el("details", { open: "" }, [el("summary", { text: "Test functions (" + t.functions.length + ")" }), el("ul", {}, t.functions.map(function (x) { return el("li", {}, [el("code", { text: x })]); }))]));
    box.appendChild(el("details", { open: "" }, [el("summary", { text: "Code" + (t.code_truncated ? " (truncated)" : "") }), el("pre", { text: t.code || "(empty)" })]));
    box.scrollIntoView({ block: "nearest" });
  }

  function draw() {
    var q = document.getElementById("q").value.trim().toLowerCase(), fl = document.getElementById("flag").value, mo = document.getElementById("module").value;
    var un = document.getElementById("unlisted").checked, fa = document.getElementById("failing").checked;
    var rows = tests.filter(function (t) {
      return (!q || t.name.toLowerCase().indexOf(q) >= 0 || (t.title || "").toLowerCase().indexOf(q) >= 0) && (!fl || (t.flags || []).indexOf(fl) >= 0) &&
             (!mo || (t.modules || []).indexOf(mo) >= 0) && (!un || t.in_runner === false) && (!fa || (t.last_rc !== null && t.last_rc !== undefined && t.last_rc !== 0));
    }).sort(function (a, b) { return a.num - b.num; });
    var table = document.getElementById("table");
    while (table.firstChild) table.removeChild(table.firstChild);
    var head = el("tr", {}, ["#", "test", "about", "modules", "flags", "runner", "first", "last", "result", ""].map(function (h) { return el("th", { text: h }); }));
    table.appendChild(el("thead", {}, [head]));
    var body = el("tbody");
    rows.forEach(function (t) {
      body.appendChild(el("tr", {}, [
        el("td", {}, [nr(t)]), el("td", {}, [el("code", { text: t.name })]), el("td", { text: t.title || "" }), el("td", { text: (t.modules || []).join(", ") }),
        el("td", {}, [flags(t.flags)]), el("td", {}, [runner(t)]), el("td", { text: day(t.first_commit) }), el("td", { text: day(t.last_commit) }), el("td", {}, [result(t)]),
        el("td", {}, [el("button", { type: "button", "class": "secondary", text: "Open", onclick: function () { open(t); } })]),
      ]));
    });
    if (!rows.length) body.appendChild(el("tr", {}, [el("td", { colspan: "10", "class": "muted", text: "No tests match these filters." })]));
    table.appendChild(body);
  }

  summary();
  ["q", "flag", "module", "unlisted", "failing"].forEach(function (id) { document.getElementById(id).addEventListener(id === "q" ? "input" : "change", draw); });
  draw();
})();
</script>
</body>
</html>
"""


def _json_for_script(obj: Any) -> str:
    """JSON that is safe inside a <script> element: ASCII only and no raw '<' (so no '</script>' or '<!--')."""
    return json.dumps(obj, ensure_ascii=True).replace("<", "\\u003c")


def render(catalogue: dict[str, Any]) -> str:
    """Return the complete HTML page for a catalogue produced by :func:`testslope.scanner.scan`."""
    project = str(catalogue.get("project", "project")).replace("&", "&amp;").replace("<", "&lt;")
    values = {"PROJECT": project, "FLAG_HELP": _json_for_script(FLAG_HELP), "RISK": _json_for_script(list(RISK_FLAGS)), "DATA": _json_for_script(catalogue)}
    return re.sub(r"__(PROJECT|FLAG_HELP|RISK|DATA)__", lambda m: values[m.group(1)], TEMPLATE)  # one pass: inserted data is never re-scanned
