"""Command line: ``testslope scan``, ``testslope report`` and ``testslope build`` (scan + report in one step)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .report import render
from .scanner import scan


def _scan_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("path", nargs="?", default=".", help="project root (default: current directory)")
    p.add_argument("--tests", default="tests", help="tests directory relative to the root (default: tests)")
    p.add_argument("--pattern", default="test_*.py", help="test file glob (default: test_*.py)")
    p.add_argument("--runner", action="append", default=[], metavar="FILE",
                   help="runner script (Makefile, tox.ini, shell script) used to mark tests it never mentions; repeatable")
    p.add_argument("--junit", metavar="XML", help="JUnit XML of a previous run (pytest --junitxml) to attach outcomes and timings")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="testslope", description="A static report of a Python test suite.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan", help="scan a project and write the catalogue as JSON")
    _scan_args(s)
    s.add_argument("--out", default="testslope.json", help="output JSON (default: testslope.json)")
    r = sub.add_parser("report", help="render a catalogue JSON as one self-contained HTML file")
    r.add_argument("catalogue", help="JSON written by 'testslope scan'")
    r.add_argument("--out", default="testslope.html", help="output HTML (default: testslope.html)")
    b = sub.add_parser("build", help="scan and render in one step")
    _scan_args(b)
    b.add_argument("--out", default="testslope.html", help="output HTML (default: testslope.html)")
    a = ap.parse_args(argv)

    if a.cmd == "report":
        data = json.loads(Path(a.catalogue).read_text(encoding="utf-8"))
    else:
        data = scan(a.path, a.tests, a.pattern, a.runner or None, a.junit)
    if a.cmd == "scan":
        Path(a.out).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    else:
        Path(a.out).write_text(render(data), encoding="utf-8")
    tests = data["tests"]
    unlisted = sum(1 for t in tests if t.get("in_runner") is False)
    print(f"{len(tests)} tests, {unlisted} not mentioned by the runner, written to {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
