"""Report and CLI: self-contained page, safe embedding of hostile text, textContent only, CLI round trip on the bundled example."""
import json
import re
from pathlib import Path

from testslope import render, scan
from testslope.cli import main

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / "example"


def _embedded(html: str) -> dict:
    return json.loads(re.search(r'<script id="data" type="application/json">(.*?)</script>', html, re.S).group(1))


def test_render_embeds_catalogue_and_has_no_external_requests():
    cat = scan(EXAMPLE, runner_files=["run_tests.sh"])
    html = render(cat)
    assert _embedded(html)["project"] == "example" and len(_embedded(html)["tests"]) == 4
    assert not re.search(r"""(?:src|href)\s*=\s*["']https?://""", html) and "@import" not in html, "the page works offline"


def test_hostile_text_cannot_break_out_of_the_page():
    cat = {"schema": 1, "project": "<b>x</b>", "generated_at": "2026-01-01T00:00:00+00:00", "runner_files": [],
           "tests": [{"name": "test_x", "path": "tests/test_x.py", "num": 1, "title": "</script><script>alert(1)</script>", "doc": "", "functions": [], "modules": [], "flags": [],
                      "lines": 1, "asserts": 0, "code": "<!-- </script> -->  ", "code_truncated": False, "preview": "<img src=x onerror=alert(1)>",
                      "first_commit": None, "last_commit": None, "commits": 0, "in_runner": None, "last_rc": None, "last_seconds": None}]}
    html = render(cat)
    assert html.count("</script>") == html.count("<script") and "<img src=x" not in html and "<b>x</b>" not in html
    assert _embedded(html)["tests"][0]["title"] == "</script><script>alert(1)</script>", "data survives the round trip intact"
    assert not re.search(r"\.(innerHTML|outerHTML)\s*=|insertAdjacentHTML\(|document\.write\(", html), "data only through textContent"


def test_cli_build_on_the_example_marks_the_orphan(tmp_path, capsys):
    out = tmp_path / "r.html"
    assert main(["build", str(EXAMPLE), "--runner", "run_tests.sh", "--out", str(out)]) == 0
    assert "4 tests, 1 not mentioned by the runner" in capsys.readouterr().out
    by = {t["name"]: t for t in _embedded(out.read_text(encoding="utf-8"))["tests"]}
    assert by["test_orphan"]["in_runner"] is False and by["test_pricing"]["in_runner"] is True
    assert by["test_cart"]["flags"] == ["sleep", "random"] and by["test_clock"]["flags"] == ["clock"] and by["test_pricing"]["flags"] == []


def test_cli_scan_then_report(tmp_path):
    cat, html = tmp_path / "c.json", tmp_path / "r.html"
    assert main(["scan", str(EXAMPLE), "--out", str(cat)]) == 0 and main(["report", str(cat), "--out", str(html)]) == 0
    assert json.loads(cat.read_text())["schema"] == 1 and "testslope: example" in html.read_text(encoding="utf-8")
