"""Scanner: docstring, functions, project modules, flags, numbering, runner mentions, JUnit results, git dates."""
import subprocess
import textwrap
from pathlib import Path

from testslope import scanner as sc

SAMPLE = '''"""Checks division and the clock. Second sentence is not part of the title."""
import json
import random
import time

from shop import cart

random.seed(1)
time.sleep(0.01)


def test_one():
    assert json.dumps({}) == "{}"
    assert cart is not None


async def test_async_one():
    assert True
'''


def test_parse_test_extracts_facts():
    it = sc.parse_test("test_sample", "tests/test_sample.py", SAMPLE, {"shop"})
    assert it["title"] == "Checks division and the clock."
    assert it["functions"] == ["test_one", "test_async_one"]
    assert it["modules"] == ["shop"]  # json, time, random are not project modules
    assert it["flags"] == ["sleep"]  # random with a seed is repeatable
    assert it["asserts"] == 3
    assert it["preview"].startswith("import json") and '"""' not in it["preview"]


def test_flags_without_seed_and_with_clock():
    unseeded = SAMPLE.replace("random.seed(1)", "random.random()")
    assert sc.parse_test("t", "p", unseeded, set())["flags"] == ["sleep", "random"]
    assert "clock" in sc.parse_test("t", "p", "import time\nx = time.time()\n", set())["flags"]
    assert "clock" in sc.parse_test("t", "p", "from datetime import datetime\nx = datetime.now()\n", set())["flags"]


def test_broken_and_huge_files_do_not_break_the_scan():
    assert sc.parse_test("t", "p", "def broken(:\n", set())["asserts"] == 0
    big = sc.parse_test("t", "p", "x = 1\n" * 20000, set())
    assert big["code_truncated"] is True and len(big["code"]) == sc.CODE_MAX


def test_numbering_follows_creation_order_with_name_tiebreak():
    items = [{"name": "b", "first_commit": "2026-02-01"}, {"name": "a", "first_commit": "2026-02-01"}, {"name": "c", "first_commit": "2026-01-01"}, {"name": "z", "first_commit": None}]
    sc.number(items)
    assert {i["name"]: i["num"] for i in items} == {"c": 1, "a": 2, "b": 3, "z": 4}


def test_mentioned_in_matches_whole_names_only():
    assert sc.mentioned_in("test_core", "python -m pytest tests/test_core.py")
    assert not sc.mentioned_in("test_core", "tests/test_core_extra.py")
    assert not sc.mentioned_in("test_core", "xtest_core.py")


def test_read_junit(tmp_path):
    xml = tmp_path / "r.xml"
    xml.write_text(textwrap.dedent("""\
        <testsuites><testsuite>
          <testcase classname="tests.test_a" name="t1" time="0.5"/>
          <testcase classname="tests.test_a" name="t2" time="0.25"><failure message="x"/></testcase>
          <testcase classname="tests.test_b.TestK" name="t3" time="1"/>
        </testsuite></testsuites>"""))
    assert sc.read_junit(xml) == {"test_a": (1, 0.75), "test_b": (0, 1.0)}


def _project(tmp_path: Path) -> Path:
    (tmp_path / "shop").mkdir()
    (tmp_path / "shop" / "__init__.py").write_text("")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_one.py").write_text('"""One."""\nfrom shop import x\n\n\ndef test_a():\n    assert True\n')
    (tmp_path / "tests" / "test_two.py").write_text("def test_b():\n    assert True\n")
    (tmp_path / "run.sh").write_text("pytest tests/test_one.py\n")
    return tmp_path


def test_scan_project_with_runner_and_without(tmp_path):
    root = _project(tmp_path)
    cat = sc.scan(root, runner_files=["run.sh"])
    by = {t["name"]: t for t in cat["tests"]}
    assert set(by) == {"test_one", "test_two"} and by["test_one"]["modules"] == ["shop"]
    assert by["test_one"]["in_runner"] is True and by["test_two"]["in_runner"] is False
    assert {t["num"] for t in cat["tests"]} == {1, 2} and cat["schema"] == 1 and cat["project"] == root.name
    assert all(t["in_runner"] is None for t in sc.scan(root)["tests"]), "no runner given means unknown, not 'not listed'"


def test_git_dates_for_tracked_and_untracked_files(tmp_path):
    root = _project(tmp_path)
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.test", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.test", "PATH": __import__("os").environ["PATH"]}
    run = lambda *a, **kw: subprocess.run(["git", *a], cwd=root, check=True, capture_output=True, env={**env, **kw.get("env", {})})  # noqa: E731
    run("init", "-q")
    run("add", "tests/test_one.py")
    run("commit", "-q", "-m", "one", env={"GIT_AUTHOR_DATE": "2026-01-02T10:00:00+00:00", "GIT_COMMITTER_DATE": "2026-01-02T10:00:00+00:00"})
    (root / "tests" / "test_one.py").write_text('"""One."""\nfrom shop import x\n\n\ndef test_a():\n    assert 1 == 1\n')
    run("add", "tests/test_one.py")
    run("commit", "-q", "-m", "two", env={"GIT_AUTHOR_DATE": "2026-03-04T10:00:00+00:00", "GIT_COMMITTER_DATE": "2026-03-04T10:00:00+00:00"})
    first, last, n = sc.git_dates(root, "tests/test_one.py")
    assert first.startswith("2026-01-02") and last.startswith("2026-03-04") and n == 2
    assert sc.git_dates(root, "tests/test_two.py") == (None, None, 0), "untracked file has no history"
    assert sc.git_dates(root / "shop" / "nope", "x.py") == (None, None, 0), "missing directory does not raise"
