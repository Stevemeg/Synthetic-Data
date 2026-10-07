from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...core.errors import AppError
from ..models import Artifact, AuditEvent, Dataset, EvaluationRun, GenerationJob, Project


def page(session: Session, statement, limit: int, offset: int):
    total = session.scalar(select(func.count()).select_from(statement.subquery()))
    items = list(session.scalars(statement.limit(limit).offset(offset)))
    return {"items": items, "total": total, "limit": limit, "offset": offset}


class ProjectRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(self, project_id: UUID, shared_lock=False) -> Project:
        query = select(Project).where(Project.id == project_id)
        if shared_lock:
            query = query.with_for_update(read=True)
        result = self.session.scalar(query)
        if result is None:
            raise AppError("Project does not exist", "PROJECT_NOT_FOUND", 404)
        return result

    def list(self, limit: int, offset: int):
        return page(
            self.session,
            select(Project).order_by(Project.created_at.desc(), Project.id),
            limit,
            offset,
        )

    def add(self, project: Project):
        self.session.add(project)
        self.session.flush()


class DatasetRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(self, dataset_id: UUID) -> Dataset:
        result = self.session.get(Dataset, dataset_id)
        if result is None:
            raise AppError("Dataset does not exist", "DATASET_NOT_FOUND", 404)
        return result

    def list(self, project_id: UUID, limit: int, offset: int):
        return page(
            self.session,
            select(Dataset)
            .where(Dataset.project_id == project_id)
            .order_by(Dataset.created_at.desc(), Dataset.id),
            limit,
            offset,
        )

    def add(self, dataset: Dataset):
        self.session.add(dataset)
        self.session.flush()


class ArtifactRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(self, artifact_id: UUID) -> Artifact:
        result = self.session.get(Artifact, artifact_id)
        if result is None:
            raise AppError("Artifact does not exist", "ARTIFACT_NOT_FOUND", 404)
        return result

    def list(self, job_id: UUID, limit: int, offset: int):
        if self.session.get(GenerationJob, job_id) is None:
            raise AppError("Job does not exist", "JOB_NOT_FOUND", 404)
        return page(
            self.session,
            select(Artifact)
            .where(Artifact.job_id == job_id)
            .order_by(Artifact.created_at, Artifact.id),
            limit,
            offset,
        )


class AuditRepository:
    def __init__(self, session: Session):
        self.session = session

    def record(
        self, event: str, entity_type: str, entity_id: UUID, actor="anonymous", metadata=None
    ):
        org = self.session.info.get("organization_id")
        user = self.session.info.get("user_id")
        if org is None:
            model = {
                "project": Project,
                "dataset": Dataset,
                "job": GenerationJob,
                "generation_job": GenerationJob,
                "evaluation": EvaluationRun,
                "evaluation_run": EvaluationRun,
            }.get(entity_type)
            if model:
                resource = self.session.get(model, entity_id)
                if resource:
                    project = (
                        resource
                        if model is Project
                        else self.session.get(Project, resource.project_id)
                    )
                    org = project.organization_id if project else None
        if user is not None and actor == "anonymous":
            actor = "user"
        self.session.add(
            AuditEvent(
                event_type=event,
                entity_type=entity_type,
                entity_id=entity_id,
                actor=actor,
                user_id=user if actor == "user" else None,
                organization_id=org,
                request_id=self.session.info.get("request_id"),
                metadata_json=metadata or {},
            )
        )
