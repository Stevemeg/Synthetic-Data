from fastapi import APIRouter

from ...core.errors import AppError
from ...core.logging import log_event
from ...schemas.platform import CapabilitiesRead, HealthRead, ReadyRead
from ...services.capabilities import capabilities
from ..dependencies import RuntimeDep
from ..errors import ERRORS

router = APIRouter(tags=["Health"])


@router.get("/api/v1/version", summary="Inspect release identity")
def release_identity(runtime: RuntimeDep):
    settings = runtime.settings
    return {
        "version": settings.app_version,
        "commit": settings.app_commit,
        "build_timestamp": settings.app_build_timestamp,
    }


@router.get("/health", response_model=HealthRead, summary="Check whether this API process is alive")
def health():
    return HealthRead()


@router.get(
    "/ready",
    response_model=ReadyRead,
    responses=ERRORS,
    summary="Check migrated PostgreSQL and artifact storage",
)
def ready(runtime: RuntimeDep):
    try:
        runtime.database.ready()
        runtime.store.ready()
    except Exception as error:
        log_event("readiness_failed", exception_type=type(error).__name__)
        raise AppError(
            "Database migrations or artifact storage are unavailable", "DEPENDENCY_UNAVAILABLE", 503
        ) from error
    return ReadyRead(ready=True)


@router.get(
    "/api/v1/capabilities",
    response_model=CapabilitiesRead,
    summary="Inspect workflow maturity, availability, and limits",
)
def get_capabilities(runtime: RuntimeDep):
    return capabilities(runtime.settings)
