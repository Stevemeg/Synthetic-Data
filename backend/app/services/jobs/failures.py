from dataclasses import dataclass, field

from botocore.exceptions import BotoCoreError, ClientError
from sqlalchemy.exc import OperationalError

from ...core.errors import AppError


@dataclass(frozen=True)
class JobFailure:
    code: str
    message: str
    retryable: bool
    diagnostics: dict = field(default_factory=dict)


def classify_failure(error: Exception) -> JobFailure:
    if isinstance(error, AppError):
        mapping = {"invalid_ecg": "DATASET_INVALID", "unavailable": "ENGINE_NOT_AVAILABLE"}
        code = mapping.get(error.code, error.code.upper())
        # Source/engine errors are deterministic; their safe AppError text is intentionally authored.
        return JobFailure(code, str(error)[:500], False, getattr(error, "diagnostics", {}))
    if isinstance(error, FileNotFoundError):
        return JobFailure(
            "INPUT_OR_MODEL_MISSING", "Required input or model bytes are unavailable", False
        )
    if isinstance(error, (OperationalError, OSError, BotoCoreError)) or (
        isinstance(error, ClientError)
        and error.response.get("ResponseMetadata", {}).get("HTTPStatusCode", 0) >= 500
    ):
        return JobFailure(
            "TRANSIENT_IO_ERROR", "A temporary database or storage operation failed", True
        )
    return JobFailure(
        "GENERATION_FAILED", "Generation failed without publishing a completed artifact set", False
    )
