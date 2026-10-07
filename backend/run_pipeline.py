"""Compatibility CLI for the modular ECG service."""

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.scripts.run_pipeline import main, run_full_pipeline  # noqa: F401

if __name__ == "__main__":
    main()
