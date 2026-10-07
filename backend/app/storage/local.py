import hashlib
import os
import re
from pathlib import Path, PurePosixPath
from tempfile import NamedTemporaryFile
from typing import BinaryIO

from ..core.errors import AppError
from .base import StoredObject


def hash_stream(source: BinaryIO) -> StoredObject:
    digest = hashlib.sha256()
    size = 0
    while chunk := source.read(65536):
        digest.update(chunk)
        size += len(chunk)
    return StoredObject(size, digest.hexdigest())


class LocalArtifactStore:
    def __init__(self, root: Path):
        if root.is_symlink():
            raise ValueError("Storage root must not be a symlink")
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, key: str) -> Path:
        parts = PurePosixPath(key).parts
        if str(PurePosixPath(key)) != key:
            raise AppError("Storage keys must be canonical", "INVALID_STORAGE_KEY")
        if (
            not parts
            or "\\" in key
            or key.startswith("/")
            or any(
                part in {".", ".."} or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,120}", part)
                for part in parts
            )
            or "//" in key
            or "/./" in key
        ):
            raise AppError("Invalid storage key", "INVALID_STORAGE_KEY")
        candidate = self.root.joinpath(*parts)
        for parent in (candidate, *candidate.parents):
            if parent == self.root:
                break
            if parent.is_symlink():
                raise AppError("Invalid storage boundary", "INVALID_STORAGE_KEY")
        if not candidate.resolve().is_relative_to(self.root):
            raise AppError("Invalid storage boundary", "INVALID_STORAGE_KEY")
        return candidate

    def put(self, key: str, source: BinaryIO) -> StoredObject:
        destination = self.path(key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with NamedTemporaryFile(
                prefix=".write_", dir=destination.parent, delete=False
            ) as output:
                temporary = Path(output.name)
                digest = hashlib.sha256()
                size = 0
                while chunk := source.read(65536):
                    output.write(chunk)
                    size += len(chunk)
                    digest.update(chunk)
                output.flush()
                os.fsync(output.fileno())
            # Atomic and exclusive: never replace an existing immutable object.
            os.link(temporary, destination)
            return StoredObject(size, digest.hexdigest())
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def get(self, key: str) -> BinaryIO:
        return self.path(key).open("rb")

    def delete(self, key: str):
        self.path(key).unlink(missing_ok=True)

    def exists(self, key: str) -> bool:
        return self.path(key).is_file()

    def metadata(self, key: str) -> StoredObject:
        with self.get(key) as source:
            return hash_stream(source)

    def ready(self):
        with NamedTemporaryFile(dir=self.root):
            pass
