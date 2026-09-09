"""Pytest bootstrap: make the repo root importable so the `backend` package
(and agent_rewards) can be imported from any cwd during test collection."""

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
