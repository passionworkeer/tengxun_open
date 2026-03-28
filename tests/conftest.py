"""Pytest bootstrap for repo-local imports.

This keeps `pytest` runnable without requiring callers to export PYTHONPATH.
"""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROOT_STR = str(ROOT)
if ROOT_STR not in sys.path:
    sys.path.insert(0, ROOT_STR)
