from fastapi import APIRouter, Depends

from ..security.auth import require_access
from .routes import (
    artifacts,
    authentication,
    datasets,
    evaluations,
    health,
    jobs,
    metrics,
    organizations,
    projects,
    workspace,
)

router = APIRouter()
for routes in (health, authentication, metrics):
    router.include_router(routes.router)
for routes in (projects, datasets, jobs, artifacts, evaluations, workspace, organizations):
    router.include_router(routes.router, dependencies=[Depends(require_access)])
