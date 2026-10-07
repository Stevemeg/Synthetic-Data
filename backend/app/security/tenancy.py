"""A request-only session scopes ORM reads before they reach PostgreSQL.

Workers and migrations use ordinary sessions. No tenant session is reused across requests.
"""

from sqlalchemy import event, select
from sqlalchemy.orm import Session, with_loader_criteria

from ..core.errors import AppError
from ..db.models import (
    Artifact,
    AuditEvent,
    Dataset,
    EvaluationRun,
    GenerationJob,
    Project,
    ReleasePolicy,
)

SCOPED = (Project, Dataset, GenerationJob, EvaluationRun, ReleasePolicy, Artifact, AuditEvent)


class TenantSession(Session):
    def get(self, entity, ident, **kwargs):
        # Session.get's identity-map shortcut must not bypass the organization predicate.
        if entity in SCOPED:
            statement = select(entity).where(entity.id == ident)
            if kwargs.get("with_for_update"):
                statement = statement.with_for_update()
            return self.scalar(statement)
        return super().get(entity, ident, **kwargs)


@event.listens_for(TenantSession, "do_orm_execute")
def scope_reads(state):
    if not state.is_select:
        return
    org = state.session.info["organization_id"]
    # Core subqueries deliberately avoid recursively applying ORM loader options.
    projects = select(Project.__table__.c.id).where(
        Project.__table__.c.organization_id == org,
        Project.__table__.c.deletion_state == "ACTIVE",
    )
    jobs = select(GenerationJob.__table__.c.id).where(
        GenerationJob.__table__.c.project_id.in_(projects)
    )
    predicates = {
        Project: (Project.organization_id == org) & (Project.deletion_state == "ACTIVE"),
        AuditEvent: AuditEvent.organization_id == org,
        Artifact: Artifact.job_id.in_(jobs),
        **{
            m: m.project_id.in_(projects)
            for m in (Dataset, GenerationJob, EvaluationRun, ReleasePolicy)
        },
    }
    state.statement = state.statement.options(
        *[
            with_loader_criteria(model, predicate, include_aliases=True)
            for model, predicate in predicates.items()
        ]
    )


@event.listens_for(TenantSession, "before_flush")
def scope_writes(session, flush_context, instances):
    org = session.info["organization_id"]
    for obj in session.new:
        if isinstance(obj, Project):
            obj.organization_id = org
        elif isinstance(obj, (Dataset, GenerationJob, EvaluationRun, ReleasePolicy)):
            parent = session.connection().scalar(
                select(Project.__table__.c.id).where(
                    Project.__table__.c.id == obj.project_id,
                    Project.__table__.c.organization_id == org,
                    Project.__table__.c.deletion_state == "ACTIVE",
                )
            )
            if parent is None:
                raise AppError("Resource not found", "not_found", 404)
