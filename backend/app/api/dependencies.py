from typing import Annotated

from fastapi import Depends, Query, Request
from sqlalchemy.orm import Session

from ..core.runtime import Runtime
from ..security.auth import require_access
from ..security.tenancy import TenantSession


def runtime(request: Request) -> Runtime:
    return request.app.state.runtime


def session(request: Request):
    principal = require_access(request)
    with TenantSession(
        bind=request.app.state.runtime.database.engine,
        expire_on_commit=False,
        info={
            "organization_id": principal.organization_id,
            "user_id": principal.user_id,
            "request_id": request.state.request_id,
        },
    ) as session:
        yield session


SessionDep = Annotated[Session, Depends(session)]
RuntimeDep = Annotated[Runtime, Depends(runtime)]
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0, le=1000000)]
