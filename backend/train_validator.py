"""Compatibility wrapper for the experimental offline image classifier trainer."""

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.scripts.train_validator import main, train_validator  # noqa: F401

if __name__ == "__main__":
    main()
