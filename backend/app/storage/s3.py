"""Private S3-compatible objects with explicit SHA-256, never ETag-based integrity."""

import re
from pathlib import PurePosixPath
from tempfile import SpooledTemporaryFile
from typing import BinaryIO

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from ..config import Settings
from ..core.errors import AppError
from .base import StoredObject
from .local import hash_stream


def validate_key(key):
    parts = PurePosixPath(key).parts
    if (
        str(PurePosixPath(key)) != key
        or not parts
        or "\\" in key
        or key.startswith("/")
        or any(
            not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,120}", p) or p in {".", ".."}
            for p in parts
        )
    ):
        raise AppError("Invalid storage key", "INVALID_STORAGE_KEY")


class S3ArtifactStore:
    def __init__(self, settings: Settings):
        self.bucket = settings.s3_bucket
        self.encryption = settings.s3_server_side_encryption
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint,
            region_name=settings.s3_region,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            config=Config(
                connect_timeout=3,
                read_timeout=30,
                retries={"max_attempts": 3},
                s3={"addressing_style": "path"} if settings.s3_endpoint else {},
            ),
        )

    def put(self, key: str, source: BinaryIO) -> StoredObject:
        validate_key(key)
        # Model/report sources are already bounded by platform limits. Spool off RAM.
        with SpooledTemporaryFile(max_size=8 * 1024**2) as buffer:
            while chunk := source.read(65536):
                buffer.write(chunk)
            buffer.seek(0)
            info = hash_stream(buffer)
            buffer.seek(0)
            options = {"ServerSideEncryption": self.encryption} if self.encryption else {}
            self.client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=buffer,
                ContentLength=info.size_bytes,
                Metadata={"sha256": info.sha256},
                IfNoneMatch="*",
                **options,
            )
            return info

    def get(self, key: str) -> BinaryIO:
        validate_key(key)
        buffer = SpooledTemporaryFile(max_size=8 * 1024**2)
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=key)
            with response["Body"] as source:
                while chunk := source.read(65536):
                    buffer.write(chunk)
            buffer.seek(0)
            return buffer
        except ClientError as exc:
            buffer.close()
            if exc.response["Error"]["Code"] in {"NoSuchKey", "404", "NotFound"}:
                raise FileNotFoundError("Registered object is unavailable") from None
            raise
        except BaseException:
            buffer.close()
            raise

    def delete(self, key: str):
        validate_key(key)
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def exists(self, key: str) -> bool:
        validate_key(key)
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError as exc:
            if exc.response["Error"]["Code"] in {"404", "NoSuchKey", "NotFound"}:
                return False
            raise

    def metadata(self, key: str) -> StoredObject:
        with self.get(key) as source:
            return hash_stream(source)

    def ready(self):
        self.client.head_bucket(Bucket=self.bucket)
