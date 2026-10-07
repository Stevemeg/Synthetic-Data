from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from ...config import Settings
from ...core.errors import AppError
from ...core.logging import log_event
from ...core.security import sanitize_filename
from ...db.models import Dataset
from ...db.repositories.catalog import AuditRepository, DatasetRepository, ProjectRepository
from ...storage.base import ArtifactStore
from ...utils.ecg_input import read_ecg_csv
from ...utils.uploads import saved_csv
from ..tabular.profile import read_table


@dataclass
class CsvUpload:
    filename: str
    mimetype: str
    stream: BinaryIO


def infer_metadata(path: Path, modality: str, settings: Settings) -> tuple[int, int, dict]:
    if modality == "timeseries":
        signals = read_ecg_csv(path, settings)
        return (
            len(signals),
            signals.shape[1] + 1,
            {
                "columns": [f"signal_{index}" for index in range(signals.shape[1])]
                + ["source_label"],
                "dtypes": {"signals": "float32", "source_label": "ignored"},
                "format": "headerless_ecg_csv",
                "source_labels_used_for_generation": False,
            },
        )
    if modality != "tabular":
        raise AppError(
            "Only clinical tabular and ECG CSV registration is supported",
            "DATASET_MODALITY_UNSUPPORTED",
        )
    frame = read_table(path, settings)
    return (
        len(frame),
        frame.shape[1],
        {
            "columns": list(frame.columns),
            "dtypes": {str(c): str(t) for c, t in frame.dtypes.items()},
            "format": "headered_tabular_csv",
        },
    )


class DatasetService:
    def __init__(self, session: Session, store: ArtifactStore, settings: Settings):
        self.session = session
        self.store = store
        self.settings = settings
        self.repository = DatasetRepository(session)

    def register(self, project_id: UUID, name: str, modality: str, upload: CsvUpload):
        name = name.strip()
        if not 1 <= len(name) <= 120:
            raise AppError("Dataset name must contain 1 to 120 characters", "INVALID_DATASET_NAME")
        if modality not in {"tabular", "timeseries"}:
            raise AppError(
                "Only tabular and ECG CSV registration is supported", "DATASET_MODALITY_UNSUPPORTED"
            )
        dataset_id = uuid4()
        key = f"projects/{project_id.hex}/datasets/{dataset_id.hex}/source.csv"
        written = False
        try:
            with saved_csv(
                upload, self.settings.upload_dir, self.settings.max_upload_mb * 1024**2
            ) as source:
                rows, columns, metadata = infer_metadata(source, modality, self.settings)
                with self.session.begin():
                    project = ProjectRepository(self.session).get(project_id, shared_lock=True)
                    if project.status != "ACTIVE":
                        raise AppError("Project is archived", "PROJECT_ARCHIVED", 409)
                    with source.open("rb") as stream:
                        stored = self.store.put(key, stream)
                    written = True
                    dataset = Dataset(
                        id=dataset_id,
                        project_id=project_id,
                        name=name,
                        modality=modality,
                        original_filename=sanitize_filename(upload.filename),
                        content_type="text/csv",
                        size_bytes=stored.size_bytes,
                        sha256=stored.sha256,
                        storage_key=key,
                        status="READY",
                        row_count=rows,
                        column_count=columns,
                        metadata_json=metadata,
                    )
                    self.repository.add(dataset)
                    AuditRepository(self.session).record(
                        "DATASET_REGISTERED",
                        "dataset",
                        dataset.id,
                        metadata={
                            "project_id": str(project_id),
                            "sha256": stored.sha256,
                            "size_bytes": stored.size_bytes,
                        },
                    )
            log_event("dataset_registered", project_id=str(project_id), dataset_id=str(dataset_id))
            return dataset
        except Exception:
            if written:
                # Commit acknowledgement can be lost. Verify on a fresh session before deleting.
                try:
                    with Session(bind=self.session.get_bind()) as check:
                        persisted = check.get(Dataset, dataset_id)
                    if persisted is None:
                        self.store.delete(key)
                except Exception:
                    log_event("orphan_reconciliation_required", dataset_id=str(dataset_id))
            raise

    def get(self, dataset_id: UUID):
        return self.repository.get(dataset_id)

    def list(self, project_id: UUID, limit: int, offset: int):
        ProjectRepository(self.session).get(project_id)
        return self.repository.list(project_id, limit, offset)
