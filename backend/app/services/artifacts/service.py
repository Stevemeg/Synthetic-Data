import shutil
from tempfile import SpooledTemporaryFile
from uuid import UUID

from sqlalchemy.orm import Session

from ...core.errors import AppError
from ...core.security import sanitize_filename
from ...db.repositories.catalog import ArtifactRepository, AuditRepository
from ...schemas.platform import ArtifactRead
from ...storage.base import ArtifactStore
from ...storage.local import hash_stream


def artifact_response(artifact) -> ArtifactRead:
    filename = artifact.filename
    if not filename.startswith("medsynth-guard_"):
        filename = sanitize_filename(f"medsynth-guard_{artifact.job_id.hex[:8]}_{filename}")
    return ArtifactRead.model_validate(artifact).model_copy(
        update={
            "downloadable": artifact.artifact_type not in {"MODEL_CHECKPOINT", "SYNTHESIS_MODEL"},
            "filename": filename,
        }
    )


class ArtifactService:
    def __init__(self, session: Session, store: ArtifactStore):
        self.session = session
        self.store = store
        self.repository = ArtifactRepository(session)

    def get(self, artifact_id: UUID):
        return artifact_response(self.repository.get(artifact_id))

    def list(self, job_id: UUID, limit: int, offset: int):
        page = self.repository.list(job_id, limit, offset)
        page["items"] = [artifact_response(artifact) for artifact in page["items"]]
        return page

    def download(self, artifact_id: UUID):
        content = SpooledTemporaryFile(max_size=8 * 1024**2)
        try:
            return self._verified_download(artifact_id, content)
        except BaseException:
            content.close()
            raise

    def _verified_download(self, artifact_id: UUID, content):
        with self.session.begin():
            artifact = self.repository.get(artifact_id)
            if artifact.artifact_type in {"MODEL_CHECKPOINT", "SYNTHESIS_MODEL"}:
                raise AppError(
                    "Trained model downloads are restricted by platform policy",
                    "ARTIFACT_DOWNLOAD_RESTRICTED",
                    403,
                )
            try:
                with self.store.get(artifact.storage_key) as source:
                    shutil.copyfileobj(source, content, length=65536)
                content.seek(0)
                actual = hash_stream(content)
            except FileNotFoundError as error:
                raise AppError(
                    "Artifact bytes are unavailable", "ARTIFACT_UNAVAILABLE", 503
                ) from error
            if actual.sha256 != artifact.sha256 or actual.size_bytes != artifact.size_bytes:
                raise AppError("Artifact integrity check failed", "ARTIFACT_INTEGRITY_FAILED", 503)
            AuditRepository(self.session).record("ARTIFACT_DOWNLOADED", "artifact", artifact.id)

        def stream():
            # Return exactly the bytes verified above, without a second object retrieval.
            with content:
                content.seek(0)
                while chunk := content.read(65536):
                    yield chunk

        return artifact_response(artifact), stream()
