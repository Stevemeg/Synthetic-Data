from ..config import Settings
from .instrumented import ObservedArtifactStore
from .local import LocalArtifactStore
from .s3 import S3ArtifactStore


def artifact_store(settings: Settings):
    store = (
        S3ArtifactStore(settings)
        if settings.artifact_storage_backend == "s3"
        else LocalArtifactStore(settings.artifact_storage_path)
    )
    return ObservedArtifactStore(store, settings.artifact_storage_backend)
