"""Compatibility wrapper for backend.scripts.train_tabular_model."""

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.scripts.train_tabular_model import main, train_and_save_model  # noqa: F401

if __name__ == "__main__":
    main()
