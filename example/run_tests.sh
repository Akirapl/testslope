#!/usr/bin/env bash
# The example project's "CI" runner. It lists tests by hand, which is exactly how a test ends up never running:
# one test file exists but is not listed below, and "testslope build --runner run_tests.sh" reports it.
set -euo pipefail
cd "$(dirname "$0")"
python -m pytest tests/test_pricing.py tests/test_cart.py tests/test_clock.py
