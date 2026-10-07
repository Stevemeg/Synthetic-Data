import re
import unicodedata
from pathlib import Path

from .errors import AppError


def sanitize_filename(filename: str) -> str:
    name = unicodedata.normalize("NFKD", filename).encode("ascii", "ignore").decode()
    name = name.replace("\\", "/").split("/")[-1]
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name).strip("._")
    if not name or len(name) > 240:
        raise AppError("A filename of at most 240 characters is required", "INVALID_FILENAME")
    if Path(name).stem.upper() in {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *[f"COM{i}" for i in range(1, 10)],
        *[f"LPT{i}" for i in range(1, 10)],
    }:
        name = "_" + name
    return name
