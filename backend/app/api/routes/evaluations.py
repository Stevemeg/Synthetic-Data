from uuid import UUID

from fastapi import APIRouter

from ...schemas.evaluation import (
    ComparisonRequest,
    EvaluationCreate,
    EvaluationRead,
    PolicyCreate,
    PolicyRead,
)
from ...schemas.platform import ArtifactRead, Page
from ...services.artifacts.service import ArtifactService
from ...services.evaluation.reporting import GovernanceReportService
from ...services.evaluation.service import EvaluationService, get_policy
from ..dependencies import Limit, Offset, RuntimeDep, SessionDep
from ..errors import ERRORS

router = APIRouter(prefix="/api/v1", tags=["Tabular evaluations"], responses=ERRORS)


@router.post(
    "/generation-jobs/{job_id}/evaluations", response_model=EvaluationRead, status_code=202
)
def submit_evaluation(
    job_id: UUID, request: EvaluationCreate, session: SessionDep, runtime: RuntimeDep
):
    return EvaluationService(session, runtime.settings, runtime.store).submit(job_id, request)


@router.get("/evaluations/{evaluation_id}", response_model=EvaluationRead)
def get_evaluation(evaluation_id: UUID, session: SessionDep, runtime: RuntimeDep):
    return EvaluationService(session, runtime.settings, runtime.store).get(evaluation_id)


@router.get("/projects/{project_id}/evaluations", response_model=Page[EvaluationRead])
def list_evaluations(
    project_id: UUID,
    session: SessionDep,
    runtime: RuntimeDep,
    limit: Limit = 50,
    offset: Offset = 0,
):
    return EvaluationService(session, runtime.settings, runtime.store).list(
        project_id, limit, offset
    )


@router.get("/evaluations/{evaluation_id}/reports", response_model=Page[ArtifactRead])
def evaluation_reports(
    evaluation_id: UUID,
    session: SessionDep,
    runtime: RuntimeDep,
    limit: Limit = 50,
    offset: Offset = 0,
):
    run = EvaluationService(session, runtime.settings, runtime.store).get(evaluation_id)
    return ArtifactService(session, runtime.store).list(run.execution_job_id, limit, offset)


@router.post(
    "/evaluations/{evaluation_id}/governance-report", response_model=ArtifactRead, status_code=201
)
def governance_report(evaluation_id: UUID, session: SessionDep, runtime: RuntimeDep):
    return GovernanceReportService(session, runtime.store).create(evaluation_id)


@router.post("/projects/{project_id}/evaluations/compare")
def compare_evaluations(
    project_id: UUID, request: ComparisonRequest, session: SessionDep, runtime: RuntimeDep
):
    return EvaluationService(session, runtime.settings, runtime.store).compare(
        project_id, request.evaluation_ids
    )


@router.post("/projects/{project_id}/release-policies", response_model=PolicyRead, status_code=201)
def create_policy(
    project_id: UUID, request: PolicyCreate, session: SessionDep, runtime: RuntimeDep
):
    return EvaluationService(session, runtime.settings, runtime.store).create_policy(
        project_id, request
    )


@router.get("/projects/{project_id}/release-policies", response_model=Page[PolicyRead])
def list_policies(
    project_id: UUID,
    session: SessionDep,
    runtime: RuntimeDep,
    limit: Limit = 50,
    offset: Offset = 0,
):
    return EvaluationService(session, runtime.settings, runtime.store).policies(
        project_id, limit, offset
    )


@router.get("/release-policies/{policy_id}", response_model=PolicyRead)
def read_policy(policy_id: UUID, session: SessionDep):
    return get_policy(session, policy_id)
