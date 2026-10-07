from uuid import UUID

from sqlalchemy.orm import Session

from ...db.models import Project
from ...db.repositories.catalog import AuditRepository, ProjectRepository
from ...schemas.platform import ProjectCreate, ProjectPatch


class ProjectService:
    def __init__(self, session: Session):
        self.session = session
        self.repository = ProjectRepository(session)

    def create(self, request: ProjectCreate):
        with self.session.begin():
            project = Project(**request.model_dump())
            self.repository.add(project)
            AuditRepository(self.session).record("PROJECT_CREATED", "project", project.id)
        return project

    def get(self, project_id: UUID):
        return self.repository.get(project_id)

    def list(self, limit: int, offset: int):
        return self.repository.list(limit, offset)

    def patch(self, project_id: UUID, request: ProjectPatch):
        with self.session.begin():
            project = self.repository.get(project_id, shared_lock=False)
            for key, value in request.model_dump(exclude_unset=True).items():
                setattr(project, key, value)
            AuditRepository(self.session).record(
                "PROJECT_UPDATED",
                "project",
                project.id,
                metadata={"fields": sorted(request.model_fields_set)},
            )
            self.session.flush()
        return project
