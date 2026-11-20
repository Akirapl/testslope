# testslope

A static report of a Python test suite. It reads your tests (it never runs them) and shows, in one self-contained HTML file:

- every test file with a number (in order of creation, so adding tests never renumbers old ones) and the **first lines of code on hover**;
- what each test is about: module docstring, test functions, which of your own modules it touches;
- **risk flags** found by plain text patterns: `sleep`, randomness without a seed, wall-clock reads (the usual sources of flaky tests), plus threads, network and subprocesses;
- **git history**: first and last commit date, number of commits;
- **runner coverage**: which tests your runner script (Makefile, shell script, tox.ini) never mentions, i.e. tests that exist but nothing runs;
- the outcome and timing of a previous run, if you give it a JUnit XML file.

No server, no database, no dependencies, no network requests. The page inserts all data with `textContent`, so hostile text in a test cannot inject markup.

## Try it

```bash
pip install -e .
python -m testslope build example --runner run_tests.sh --out report.html
```

Open `report.html`. The bundled `example/` project has three deliberately bad tests (one sleeps and uses unseeded randomness, one reads the clock, one is never run by its runner script), and the report flags all three. A pre-built copy is in [docs/sample-report.html](docs/sample-report.html).

For your own project:

```bash
testslope build path/to/project --tests tests --runner Makefile --junit junit.xml --out report.html
testslope scan  path/to/project --out testslope.json      # just the catalogue, as JSON
testslope report testslope.json --out report.html         # render a catalogue
```

## Why this exists

This started inside a larger project that is built mostly by AI coding agents. An audit of its 170+ test scripts found things nobody had noticed: tests that no CI job ever ran, a dozen tests that slept for real time, tests that depended on the wall clock, and project rules ("invariants") that had almost no tests. Agents write tests one at a time, without a picture of the whole suite, so the whole suite drifts. testslope is the picture.

Two rules came out of it:

1. Tests are **data to look at**, not only code to run. A catalogue you can open and skim beats a green checkmark.
2. Heuristics are **hints, not verdicts**. Flags are text patterns; "not in runner" means "no script mentions this file", not "this test is useless".

## What it does not do (yet)

- It does not execute tests or measure coverage; attach a JUnit file for outcomes and use `coverage.py` for coverage.
- It does not judge whether a test is good. Planned: an optional step that asks a language model typed yes/no questions about a change (does it touch this project rule, does a test cover it) and reports the answers *with probabilities*, as advice rather than a gate. The model is a plug-in; the report works without one.
- Python only, files named `test_*.py` (`pytest` or plain scripts with `assert`).

## Development

```bash
pip install -e ".[dev]"
ruff check .
pytest
```

The package is standard library only. `ruff` bans `time.sleep` in this repository's own tests, because a tool that reports on sleeping tests should not have any.

## License

MIT, see [LICENSE](LICENSE).
