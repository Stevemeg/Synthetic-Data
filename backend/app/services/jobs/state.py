from enum import StrEnum

from ...core.errors import AppError


class JobStatus(StrEnum):
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


TRANSITIONS = {
    JobStatus.PENDING: {JobStatus.QUEUED, JobStatus.CANCELLED},
    JobStatus.QUEUED: {JobStatus.RUNNING, JobStatus.CANCELLED},
    JobStatus.RUNNING: {JobStatus.SUCCEEDED, JobStatus.FAILED},
    JobStatus.FAILED: {JobStatus.QUEUED},
    JobStatus.SUCCEEDED: set(),
    JobStatus.CANCELLED: set(),
}


def validate_transition(source: str, target: str):
    try:
        allowed = JobStatus(target) in TRANSITIONS[JobStatus(source)]
    except ValueError:
        allowed = False
    if not allowed:
        raise AppError("Illegal job state transition", "INVALID_JOB_TRANSITION", 409)
