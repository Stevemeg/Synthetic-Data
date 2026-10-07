import logging
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

from ..core.errors import AppError
from ..core.security import sanitize_filename

logger = logging.getLogger(__name__)
CSV_MIMES = {
    "text/csv",
    "text/plain",
    "application/csv",
    "application/vnd.ms-excel",
    "application/octet-stream",
    "",
}


@contextmanager
def saved_csv(upload, upload_dir: Path, max_bytes: int):
    name = sanitize_filename(upload.filename or "")
    if not name or Path(name).suffix.lower() != ".csv":
        raise AppError("Source file must have a .csv extension", "invalid_extension")
    if upload.mimetype not in CSV_MIMES:
        raise AppError("Unsupported source MIME type", "invalid_format")
    upload_dir.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="request_", dir=upload_dir) as directory:
        path = Path(directory) / name
        size = 0
        with path.open("wb") as destination:
            while chunk := upload.stream.read(65536):
                size += len(chunk)
                if size > max_bytes:
                    raise AppError("Source file exceeds upload limit", "upload_too_large", 413)
                if b"\x00" in chunk:
                    raise AppError("Source file must be text CSV", "invalid_format")
                destination.write(chunk)
        if size == 0:
            raise AppError("Source dataset is empty", "empty_dataset")
        logger.info("upload_saved extension=.csv bytes=%s", size)
        yield path
