"""Bounded product inventories and aggregate summaries; no source values or worker internals."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter
from sqlalchemy import func, or_, select

from ...db.models import Artifact, AuditEvent, Dataset, EvaluationRun, GenerationJob, Project
from ...db.repositories.catalog import ProjectRepository, page
from ...schemas.evaluation import EvaluationRead
from ...schemas.platform import ArtifactRead, DatasetRead, JobRead, Page, ProjectRead
from ...services.artifacts.service import artifact_response
from ...services.evaluation.service import evaluation_response
from ..dependencies import Limit, Offset, SessionDep

router = APIRouter(prefix="/api/v1/workspace", tags=["Workspace"])


def project_summaries(session, statement, limit, offset):
    result = page(session, statement, limit, offset)
    ids = [p.id for p in result["items"]]
    counts = {}
    for name, model, criteria in (
        ("datasets", Dataset, True),
        ("runs", GenerationJob, GenerationJob.job_kind == "GENERATION"),
        ("evaluations", EvaluationRun, True),
    ):
        counts[name] = dict(
            session.execute(
                select(model.project_id, func.count())
                .where(model.project_id.in_(ids), criteria)
                .group_by(model.project_id)
            ).all()
        )
    counts["reports"] = dict(
        session.execute(
            select(GenerationJob.project_id, func.count())
            .join(Artifact, Artifact.job_id == GenerationJob.id)
            .where(GenerationJob.project_id.in_(ids), Artifact.artifact_type == "GOVERNANCE_REPORT")
            .group_by(GenerationJob.project_id)
        ).all()
    )
    recent = select(
        EvaluationRun.project_id,
        EvaluationRun.result_summary_json,
        func.row_number()
        .over(partition_by=EvaluationRun.project_id, order_by=EvaluationRun.created_at.desc())
        .label("rank"),
    ).where(EvaluationRun.project_id.in_(ids), EvaluationRun.result_summary_json != {})
    sub = recent.subquery()
    decisions = {
        pid: summary.get("release", {}).get("decision")
        for pid, summary in session.execute(
            select(sub.c.project_id, sub.c.result_summary_json).where(sub.c.rank == 1)
        )
    }
    # Include terminal and governance events, not merely resource creation.
    entities = (
        select(Project.id.label("project_id"), Project.id.label("entity_id"))
        .where(Project.id.in_(ids))
        .union_all(
            *(
                select(model.project_id, model.id).where(model.project_id.in_(ids))
                for model in (Dataset, GenerationJob, EvaluationRun)
            )
        )
        .subquery()
    )
    activity = dict(
        session.execute(
            select(entities.c.project_id, func.max(AuditEvent.created_at))
            .join(AuditEvent, AuditEvent.entity_id == entities.c.entity_id)
            .group_by(entities.c.project_id)
        ).all()
    )
    result["items"] = [
        {
            **ProjectRead.model_validate(p).model_dump(mode="json"),
            **{name: values.get(p.id, 0) for name, values in counts.items()},
            "latest_decision": decisions.get(p.id),
            "latest_activity": max(activity.get(p.id, p.updated_at), p.updated_at),
        }
        for p in result["items"]
    ]
    return result


@router.get("/projects")
def projects(session: SessionDep, limit: Limit = 20, offset: Offset = 0):
    return project_summaries(
        session, select(Project).order_by(Project.created_at.desc(), Project.id), limit, offset
    )


@router.get("/projects/{project_id}/summary")
def project_summary(project_id: UUID, session: SessionDep):
    ProjectRepository(session).get(project_id)
    return project_summaries(session, select(Project).where(Project.id == project_id), 1, 0)[
        "items"
    ][0]


@router.get("/datasets", response_model=Page[DatasetRead])
def datasets(
    session: SessionDep,
    project_id: UUID | None = None,
    limit: Limit = 20,
    offset: Offset = 0,
):
    query = select(Dataset).order_by(Dataset.created_at.desc(), Dataset.id)
    if project_id:
        ProjectRepository(session).get(project_id)
        query = query.where(Dataset.project_id == project_id)
    return page(session, query, limit, offset)


@router.get("/runs", response_model=Page[JobRead])
def runs(
    session: SessionDep,
    project_id: UUID | None = None,
    dataset_id: UUID | None = None,
    status: Literal["PENDING", "QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELLED"]
    | None = None,
    engine: str | None = None,
    sort: Literal["asc", "desc"] = "desc",
    limit: Limit = 20,
    offset: Offset = 0,
):
    query = select(GenerationJob).where(GenerationJob.job_kind == "GENERATION")
    for column, value in (
        (GenerationJob.project_id, project_id),
        (GenerationJob.dataset_id, dataset_id),
        (GenerationJob.status, status),
        (GenerationJob.engine, engine),
    ):
        if value is not None:
            query = query.where(column == value)
    order = GenerationJob.created_at.asc() if sort == "asc" else GenerationJob.created_at.desc()
    return page(session, query.order_by(order, GenerationJob.id), limit, offset)


@router.get("/evaluations", response_model=Page[EvaluationRead])
def evaluations(
    session: SessionDep,
    project_id: UUID | None = None,
    limit: Limit = 20,
    offset: Offset = 0,
):
    query = select(EvaluationRun).order_by(EvaluationRun.created_at.desc(), EvaluationRun.id)
    if project_id:
        query = query.where(EvaluationRun.project_id == project_id)
    result = page(session, query, limit, offset)
    jobs = {
        j.id: j
        for j in session.scalars(
            select(GenerationJob).where(
                GenerationJob.id.in_([r.execution_job_id for r in result["items"]])
            )
        )
    }
    result["items"] = [
        evaluation_response(session, r, jobs[r.execution_job_id]) for r in result["items"]
    ]
    return result


@router.get("/reports", response_model=Page[ArtifactRead])
def reports(
    session: SessionDep,
    project_id: UUID | None = None,
    limit: Limit = 20,
    offset: Offset = 0,
):
    query = select(Artifact).where(Artifact.artifact_type == "GOVERNANCE_REPORT")
    if project_id:
        query = query.join(GenerationJob).where(GenerationJob.project_id == project_id)
    result = page(session, query.order_by(Artifact.created_at.desc(), Artifact.id), limit, offset)
    result["items"] = [artifact_response(a) for a in result["items"]]
    return result


@router.get("/activity")
def activity(
    session: SessionDep,
    project_id: UUID | None = None,
    entity_id: UUID | None = None,
    limit: Limit = 20,
    offset: Offset = 0,
):
    # Deliberately omit metadata_json, which can include implementation diagnostics.
    query = select(AuditEvent)
    if entity_id:
        query = query.where(AuditEvent.entity_id == entity_id)
    if project_id:
        ProjectRepository(session).get(project_id)
        query = query.where(
            or_(
                AuditEvent.entity_id == project_id,
                AuditEvent.entity_id.in_(
                    select(Dataset.id).where(Dataset.project_id == project_id)
                ),
                AuditEvent.entity_id.in_(
                    select(GenerationJob.id).where(GenerationJob.project_id == project_id)
                ),
                AuditEvent.entity_id.in_(
                    select(EvaluationRun.id).where(EvaluationRun.project_id == project_id)
                ),
                AuditEvent.entity_id.in_(
                    select(Artifact.id)
                    .join(GenerationJob)
                    .where(GenerationJob.project_id == project_id)
                ),
            )
        )
    result = page(
        session, query.order_by(AuditEvent.created_at.desc(), AuditEvent.id), limit, offset
    )
    result["items"] = [
        {
            key: getattr(event, key)
            for key in (
                "id",
                "event_type",
                "entity_type",
                "entity_id",
                "actor",
                "user_id",
                "organization_id",
                "request_id",
                "created_at",
            )
        }
        for event in result["items"]
    ]
    return result


@router.get("/projects/{project_id}/policy-usage")
def policy_usage(project_id: UUID, session: SessionDep):
    ProjectRepository(session).get(project_id)
    return {
        str(policy): count
        for policy, count in session.execute(
            select(EvaluationRun.policy_id, func.count())
            .where(EvaluationRun.project_id == project_id, EvaluationRun.policy_id.is_not(None))
            .group_by(EvaluationRun.policy_id)
        )
    }
