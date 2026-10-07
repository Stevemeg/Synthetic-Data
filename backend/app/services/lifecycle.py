"""Owner-requested logical deletion; storage cleanup is performed by the worker."""

from uuid import UUID

from sqlalchemy import func, select, text

from ..core.errors import AppError
from ..core.logging import log_event
from ..db.models import Artifact, Dataset, GenerationJob, Project
from ..db.repositories.catalog import AuditRepository, ProjectRepository
from ..db.repositories.jobs import lock_key, utcnow


def request_deletion(session, project_id: UUID, confirmation: str):
    with session.begin():
        project = ProjectRepository(session).get(project_id)
        session.refresh(project, with_for_update=True)
        if confirmation != project.name:
            raise AppError(
                "Enter the project name to confirm deletion", "confirmation_required", 422
            )
        pending = session.scalar(
            select(func.count())
            .select_from(GenerationJob)
            .where(
                GenerationJob.project_id == project_id,
                GenerationJob.status.in_(["PENDING", "QUEUED", "RUNNING"]),
            )
        )
        if pending:
            raise AppError(
                "Wait for running work to finish and cancel queued work before requesting deletion",
                "active_work",
                409,
            )
        project.status = "ARCHIVED"
        project.deletion_state = "DELETION_REQUESTED"
        project.deletion_requested_at = utcnow()
        AuditRepository(session).record("PROJECT_DELETION_REQUESTED", "project", project.id)
    return {"id": str(project.id), "deletion_state": project.deletion_state}


def purge_once(database, store):
    with database.sessions() as session:
        ids = list(
            session.scalars(
                select(Project.id)
                .where(Project.deletion_state.in_(["DELETION_REQUESTED", "PURGING"]))
                .order_by(Project.deletion_requested_at)
                .limit(10)
            )
        )
    for project_id in ids:
        with database.engine.connect() as connection:
            # Dedicated namespace; no database transaction held during storage I/O.
            key = lock_key(project_id) & 0x7FFFFFFF
            if not connection.scalar(text("SELECT pg_try_advisory_lock(6006,:key)"), {"key": key}):
                continue
            connection.commit()
            try:
                with database.sessions.begin() as session:
                    project = session.get(Project, project_id)
                    if project.deletion_state == "DELETED":
                        continue
                    project.deletion_state = "PURGING"
                    org = project.organization_id
                with database.sessions() as session:
                    keys = list(
                        session.scalars(
                            select(Dataset.storage_key).where(Dataset.project_id == project_id)
                        )
                    )
                    keys += list(
                        session.scalars(
                            select(Artifact.storage_key)
                            .join(GenerationJob)
                            .where(GenerationJob.project_id == project_id)
                        )
                    )
                for object_key in keys:
                    store.delete(object_key)
                with database.sessions.begin() as session:
                    project = session.get(Project, project_id)
                    project.deletion_state, project.purged_at = "DELETED", utcnow()
                    session.info["organization_id"] = org
                    AuditRepository(session).record(
                        "PROJECT_PURGED", "project", project.id, actor="worker"
                    )
                log_event("project_purged", project_id=str(project_id), organization_id=str(org))
                return True
            finally:
                connection.rollback()
                connection.execute(text("SELECT pg_advisory_unlock(6006,:key)"), {"key": key})
                connection.commit()
    return False
