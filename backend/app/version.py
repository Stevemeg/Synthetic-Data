from pathlib import Path

APPLICATION_VERSION = (
    (Path(__file__).resolve().parents[2] / "VERSION").read_text(encoding="ascii").strip()
)
