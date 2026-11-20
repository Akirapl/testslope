"""testslope: a static report of a Python test suite (code previews, risk flags, history, runner coverage)."""
from .report import render
from .scanner import scan

__all__ = ["scan", "render"]
__version__ = "0.1.0"
