"""Scan a Python test suite into a plain, JSON-serialisable catalogue.

The scanner only reads files: it never imports or runs your tests. For every ``test_*.py`` file it records the module docstring,
the test functions, the project modules it imports, risk flags found by simple text patterns, the code itself, and (when the
project lives in a git repository) the dates of the first and last commit. Optionally it marks which tests a runner script
mentions and attaches the outcome of a previous run from a JUnit XML file.
"""
from __future__ import annotations

import ast
import re
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
CODE_MAX = 60_000
DOC_MAX = 1_500
PREVIEW_LINES = 14
PREVIEW_MAX = 900

# Patterns that usually make tests unstable (the first three) or need an environment (the rest). Plain text heuristics, not verdicts.
RISK_FLAGS = ("sleep", "random", "clock")
FLAGS: dict[str, re.Pattern[str]] = {
    "sleep": re.compile(r"\bsleep\("),
    "random": re.compile(r"\brandom\.|\buuid4\b"),
    "clock": re.compile(r"datetime\.(?:now|utcnow)|\btime\.(?:time|monotonic)\("),
    "threads": re.compile(r"\bthreading\b|ThreadPool|concurrent\.futures"),
    "network": re.compile(r"\bsocket\b|http\.server|urllib|\brequests\b|httpx|127\.0\.0\.1|localhost"),
    "subprocess": re.compile(r"\bsubprocess\b"),
}
FLAG_HELP = {
    "sleep": "waits for real time",
    "random": "randomness without a seed",
    "clock": "reads the wall clock",
    "threads": "uses threads",
    "network": "talks to the network or localhost",
    "subprocess": "starts subprocesses",
}


def local_packages(root: Path) -> set[str]:
    """Top-level names in the project that tests can import: packages (directories with .py files) and modules."""
    names: set[str] = set()
    for base in (root, root / "src"):
        if not base.is_dir():
            continue
        for p in base.iterdir():
            if p.name.startswith((".", "_")) or p.name in {"tests", "test", "venv", "node_modules"}:
                continue
            if p.is_dir() and any(p.rglob("*.py")):
                names.add(p.name)
            elif p.suffix == ".py" and not p.name.startswith("test_"):
                names.add(p.stem)
    return names


def parse_test(name: str, path: str, text: str, project: set[str]) -> dict[str, Any]:
    """Facts about one test file derived from its text alone (no git, no execution)."""
    doc = ""
    modules: set[str] = set()
    functions: list[str] = []
    asserts = 0
    try:
        tree = ast.parse(text)
        doc = ast.get_docstring(tree) or ""
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                modules.update(a.name.split(".")[0] for a in n.names)
            elif isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
                modules.add(n.module.split(".")[0])
            elif isinstance(n, ast.Assert):
                asserts += 1
            elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith("test"):
                functions.append(n.name)
    except SyntaxError:
        pass
    title = re.split(r"(?<=[.!?])\s|\n\n", doc.strip(), maxsplit=1)[0].replace("\n", " ") if doc else ""
    flags = [k for k, rx in FLAGS.items() if rx.search(text)]
    if "random" in flags and re.search(r"\bseed\(", text):
        flags.remove("random")  # seeded randomness is repeatable
    body = text
    if doc:  # the preview starts after the module docstring
        start = text.find('"""')
        end = text.find('"""', start + 3) if start != -1 else -1
        body = text[end + 3:] if end != -1 else text
    preview = "\n".join(body.strip("\n").splitlines()[:PREVIEW_LINES])[:PREVIEW_MAX]
    return {
        "name": name, "path": path, "title": title[:300], "doc": doc[:DOC_MAX], "functions": functions[:80],
        "modules": sorted(modules & project), "flags": flags,
        "lines": text.count("\n") + 1, "asserts": asserts,
        "code": text[:CODE_MAX], "code_truncated": len(text) > CODE_MAX, "preview": preview,
    }


def git_dates(root: Path, rel: str) -> tuple[str | None, str | None, int]:
    """First and last commit date of a file and the number of commits; (None, None, 0) outside git or for untracked files."""
    try:
        out = subprocess.run(["git", "log", "--format=%aI", "--", rel], cwd=root, capture_output=True, text=True, check=False, timeout=30).stdout.split()
    except (OSError, subprocess.SubprocessError):
        return None, None, 0
    return (out[-1], out[0], len(out)) if out else (None, None, 0)


def mentioned_in(name: str, runner_text: str) -> bool:
    """True when a runner script (Makefile, tox.ini, shell script) mentions ``<name>.py`` as a whole word."""
    return re.search(r"(?<![A-Za-z0-9_])" + re.escape(name) + r"\.py\b", runner_text) is not None


def read_junit(path: Path) -> dict[str, tuple[int, float]]:
    """Per test file: exit-like code (0 pass, 1 failure or error) and total seconds, from a JUnit XML file (pytest --junitxml)."""
    res: dict[str, list[float]] = {}
    for case in ET.parse(path).getroot().iter("testcase"):
        cls = case.get("classname") or ""
        stem = next((part for part in cls.split(".") if part.startswith("test_")), None) or Path(case.get("file") or "").stem
        if not stem:
            continue
        failed = case.find("failure") is not None or case.find("error") is not None
        cur = res.setdefault(stem, [0, 0.0])
        cur[0] = max(cur[0], 1 if failed else 0)
        cur[1] += float(case.get("time") or 0)
    return {k: (int(v[0]), round(v[1], 2)) for k, v in res.items()}


def number(items: list[dict[str, Any]]) -> None:
    """Number tests in order of creation (first commit, then name) so new tests never renumber old ones."""
    for i, it in enumerate(sorted(items, key=lambda x: (x["first_commit"] or "9999", x["name"])), 1):
        it["num"] = i


def scan(root: str | Path, tests_dir: str = "tests", pattern: str = "test_*.py", runner_files: list[str] | None = None,
         junit: str | Path | None = None) -> dict[str, Any]:
    """Build the catalogue for the project at ``root``."""
    root = Path(root).resolve()
    project = local_packages(root)
    runner_text = "\n".join((root / f).read_text(errors="replace") for f in (runner_files or []) if (root / f).is_file())
    results = read_junit(Path(junit)) if junit else {}
    items: list[dict[str, Any]] = []
    for p in sorted((root / tests_dir).rglob(pattern)):
        rel = p.relative_to(root).as_posix()
        it = parse_test(p.stem, rel, p.read_text(errors="replace"), project)
        it["first_commit"], it["last_commit"], it["commits"] = git_dates(root, rel)
        it["in_runner"] = mentioned_in(p.stem, runner_text) if runner_files else None  # None = no runner given, unknown
        rc, sec = results.get(p.stem, (None, None))
        it["last_rc"], it["last_seconds"] = rc, sec
        items.append(it)
    number(items)
    return {"schema": SCHEMA_VERSION, "project": root.name, "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "runner_files": runner_files or [], "tests": items}
