from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ...schemas.platform import Page, ProjectCreate, ProjectPatch, ProjectRead
from ...services.lifecycle import request_deletion
from ...services.projects.service import ProjectService
from ..dependencies import Limit, Offset, SessionDep
from ..errors import ERRORS

router = APIRouter(prefix="/api/v1/projects", tags=["Projects"], responses=ERRORS)


@router.post("", response_model=ProjectRead, status_code=201, summary="Create a persistent project")
def create_project(request: ProjectCreate, session: SessionDep):
    return ProjectService(session).create(request)


@router.get("", response_model=Page[ProjectRead], summary="List projects with bounded pagination")
def list_projects(session: SessionDep, limit: Limit = 50, offset: Offset = 0):
    return ProjectService(session).list(limit, offset)


@router.get("/{project_id}", response_model=ProjectRead, summary="Retrieve project metadata")
def get_project(project_id: UUID, session: SessionDep):
    return ProjectService(session).get(project_id)


@router.patch("/{project_id}", response_model=ProjectRead, summary="Update or archive a project")
def patch_project(project_id: UUID, request: ProjectPatch, session: SessionDep):
    return ProjectService(session).patch(project_id, request)


class DeletionRequest(BaseModel):
    confirmation: str = Field(min_length=1, max_length=120)


@router.post("/{project_id}/deletion", status_code=202)
def delete_project(project_id: UUID, request: DeletionRequest, session: SessionDep):
    return request_deletion(session, project_id, request.confirmation)
