from uuid import UUID

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from ...schemas.platform import ArtifactRead, Page
from ...services.artifacts.service import ArtifactService
from ..dependencies import Limit, Offset, RuntimeDep, SessionDep
from ..errors import ERRORS

router = APIRouter(prefix="/api/v1", tags=["Artifacts"], responses=ERRORS)


@router.get(
    "/jobs/{job_id}/artifacts",
    response_model=Page[ArtifactRead],
    summary="List persisted artifacts for a job",
)
def list_artifacts(
    job_id: UUID, session: SessionDep, runtime: RuntimeDep, limit: Limit = 50, offset: Offset = 0
):
    return ArtifactService(session, runtime.store).list(job_id, limit, offset)


@router.get(
    "/artifacts/{artifact_id}",
    response_model=ArtifactRead,
    summary="Retrieve artifact metadata and integrity hash",
)
def get_artifact(artifact_id: UUID, session: SessionDep, runtime: RuntimeDep):
    return ArtifactService(session, runtime.store).get(artifact_id)


@router.get(
    "/artifacts/{artifact_id}/download",
    response_class=StreamingResponse,
    summary="Download a registered artifact after storage and integrity validation",
)
def download_artifact(artifact_id: UUID, session: SessionDep, runtime: RuntimeDep):
    artifact, stream = ArtifactService(session, runtime.store).download(artifact_id)
    return StreamingResponse(
        stream,
        media_type=artifact.content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{artifact.filename}"',
            "Content-Length": str(artifact.size_bytes),
        },
    )
