"""Compatibility wrapper for backend.scripts.generate_images."""

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.scripts.generate_images import generate_images, main  # noqa: F401

if __name__ == "__main__":
    main()
