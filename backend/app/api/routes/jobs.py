from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Response

from ...schemas.platform import JobCreate, JobRead, Page
from ...services.jobs.service import JobService
from ..dependencies import Limit, Offset, RuntimeDep, SessionDep
from ..errors import ERRORS

router = APIRouter(prefix="/api/v1", tags=["Generation jobs"], responses=ERRORS)


@router.post(
    "/projects/{project_id}/jobs",
    response_model=JobRead,
    status_code=202,
    responses={200: {"model": JobRead}},
    summary="Queue generation without executing a model in this request",
)
def create_job(
    project_id: UUID,
    request: JobCreate,
    response: Response,
    session: SessionDep,
    runtime: RuntimeDep,
    idempotency_key: Annotated[str | None, Header(max_length=128)] = None,
):
    job, created = JobService(session, runtime.settings, runtime.store).create(
        project_id, request, idempotency_key
    )
    response.status_code = 202 if created else 200
    return job


@router.get(
    "/projects/{project_id}/jobs",
    response_model=Page[JobRead],
    summary="List generation runs in a project",
)
def list_jobs(
    project_id: UUID,
    session: SessionDep,
    runtime: RuntimeDep,
    limit: Limit = 50,
    offset: Offset = 0,
):
    return JobService(session, runtime.settings).list(project_id, limit, offset)


@router.get(
    "/jobs/{job_id}",
    response_model=JobRead,
    summary="Poll durable job state and sanitized failures",
)
def get_job(job_id: UUID, session: SessionDep, runtime: RuntimeDep):
    return JobService(session, runtime.settings).get(job_id)


@router.post(
    "/jobs/{job_id}/cancel",
    response_model=JobRead,
    summary="Cancel queued work; running models cannot be cancelled here",
)
def cancel_job(job_id: UUID, session: SessionDep, runtime: RuntimeDep):
    return JobService(session, runtime.settings).cancel(job_id)


@router.post(
    "/jobs/{job_id}/retry",
    response_model=JobRead,
    summary="Requeue an eligible transient failure within its attempt budget",
)
def retry_job(job_id: UUID, session: SessionDep, runtime: RuntimeDep):
    return JobService(session, runtime.settings).retry(job_id)
