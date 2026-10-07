"""Compatibility entry point. Prefer `python -m backend.app` from the root."""

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.__main__ import main

if __name__ == "__main__":
    main()
