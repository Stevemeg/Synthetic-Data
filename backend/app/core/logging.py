import json
import logging
from contextvars import ContextVar
from datetime import datetime, timezone

request_id_context: ContextVar[str | None] = ContextVar("request_id", default=None)
job_context: ContextVar[dict] = ContextVar("job_context", default={})
FIELDS = {
    "user_id",
    "organization_id",
    "event",
    "job_id",
    "project_id",
    "dataset_id",
    "worker_id",
    "status",
    "duration",
    "error_code",
    "exception_type",
    "attempt",
    "artifact_id",
    "request_id",
    "run_id",
    "modality",
    "engine",
    "sample_count",
}


class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "request_id": request_id_context.get(),
            # Third-party log messages can contain URLs/codes or exception payloads.
            "event": getattr(record, "event", "external_log"),
        }
        payload.update({key: getattr(record, key) for key in FIELDS if hasattr(record, key)})
        payload.update(job_context.get())
        if record.exc_info and record.exc_info[0]:
            payload["exception_type"] = record.exc_info[0].__name__
        # Never attach exception text or SQL parameters to structured output.
        return json.dumps(payload, default=str)


def configure_logging(level: str):
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=level, handlers=[handler], force=True)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def log_event(event: str, **fields):
    logging.getLogger("medsynth").info(event, extra={"event": event, **fields})
