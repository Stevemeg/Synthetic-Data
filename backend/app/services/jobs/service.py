import hashlib
import json
import re
from uuid import UUID, uuid4

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ...config import Settings
from ...core.errors import AppError
from ...core.logging import log_event
from ...db.models import GenerationJob
from ...db.repositories.catalog import AuditRepository, DatasetRepository, ProjectRepository
from ...db.repositories.jobs import JobRepository, utcnow
from ...schemas.generation import GenerationRequest
from ...schemas.platform import JobCreate
from ...storage.base import ArtifactStore
from ...storage.factory import artifact_store
from ..generation.service import GenerationService
from ..tabular.engines import available_engines
from ..tabular.service import prepare_submission


def fingerprint(request: JobCreate) -> str:
    payload = request.model_dump(mode="json")
    if request.modality != "tabular":
        for name in ("engine", "configuration", "metadata_overrides", "validation_rules"):
            payload.pop(name)
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


class JobService:
    def __init__(self, session: Session, settings: Settings, store: ArtifactStore | None = None):
        self.session = session
        self.settings = settings
        self.store = store or artifact_store(settings)
        self.repository = JobRepository(session)

    def create(self, project_id: UUID, request: JobCreate, idempotency_key: str | None):
        if idempotency_key is not None and not re.fullmatch(
            r"[A-Za-z0-9._:-]{1,128}", idempotency_key
        ):
            raise AppError(
                "Idempotency-Key must be 1 to 128 safe characters", "INVALID_IDEMPOTENCY_KEY"
            )
        digest = fingerprint(request)
        if request.modality == "tabular":
            # Cold optional ML imports must not consume a database transaction's idle timeout.
            available_engines()
        with self.session.begin():
            if idempotency_key is not None:
                existing = self.repository.by_idempotency(project_id, idempotency_key)
                if existing is not None:
                    return self._equivalent(existing, digest), False
            project = ProjectRepository(self.session).get(project_id, shared_lock=True)
            if project.status != "ACTIVE":
                raise AppError("Project is archived", "PROJECT_ARCHIVED", 409)
            if request.modality != "tabular":
                GenerationService(self.settings).ensure_available(request.modality)
            config = {"count": request.requested_samples, "seed": request.random_seed}
            if request.modality == "imaging":
                config["modality"] = request.imaging_modality
            elif request.imaging_modality is not None:
                raise AppError(
                    "imaging_modality is only valid for imaging", "INVALID_JOB_CONFIGURATION"
                )
            if request.modality != "tabular":
                GenerationRequest.parse(request.modality, config, self.settings)
            tabular_configuration = {}
            engine = "pytorch-ecg-vae" if request.modality == "timeseries" else "dcgan-64-rgb"
            if request.modality in {"timeseries", "tabular"}:
                if request.dataset_id is None:
                    raise AppError(
                        "This workflow requires a registered dataset", "DATASET_REQUIRED"
                    )
                dataset = DatasetRepository(self.session).get(request.dataset_id)
                if (
                    dataset.project_id != project_id
                    or dataset.modality != request.modality
                    or dataset.status != "READY"
                ):
                    raise AppError("Dataset does not belong to this workflow", "DATASET_MISMATCH")
                if request.modality == "tabular":
                    engine, tabular_configuration = prepare_submission(
                        dataset, self.store, self.settings, request
                    )
            elif request.dataset_id is not None:
                raise AppError(
                    "Imaging is unconditional and does not accept a source dataset",
                    "SOURCE_CONDITIONING_UNSUPPORTED",
                )
            configuration = {
                **config,
                "ecg_epochs": self.settings.ecg_epochs,
                "ecg_sampling_rate": self.settings.ecg_sampling_rate,
                "max_ecg_segments": self.settings.max_ecg_segments,
                "max_source_rows": self.settings.max_source_rows,
                "max_upload_mb": self.settings.max_upload_mb,
                "max_samples": self.settings.max_samples,
                "max_images": self.settings.max_images,
                **tabular_configuration,
            }
            values = dict(
                id=uuid4(),
                project_id=project_id,
                dataset_id=request.dataset_id,
                modality=request.modality,
                engine=engine,
                status="PENDING",
                requested_samples=request.requested_samples,
                produced_samples=0,
                random_seed=request.random_seed,
                configuration_json=configuration,
                attempt_count=0,
                max_attempts=self.settings.job_max_attempts,
                metadata_json={},
                idempotency_key=idempotency_key,
                request_fingerprint=digest,
            )
            statement = insert(GenerationJob).values(**values)
            if idempotency_key is not None:
                statement = statement.on_conflict_do_nothing(
                    constraint="uq_jobs_project_idempotency"
                )
            job_id = self.session.scalar(statement.returning(GenerationJob.id))
            if job_id is None:
                return self._equivalent(
                    self.repository.by_idempotency(project_id, idempotency_key), digest
                ), False
            job = self.repository.get(job_id)
            AuditRepository(self.session).record(
                "TABULAR_JOB_SUBMITTED" if request.modality == "tabular" else "JOB_CREATED",
                "job",
                job.id,
                metadata={
                    "project_id": str(project_id),
                    "dataset_id": str(request.dataset_id) if request.dataset_id else None,
                },
            )
            job.queued_at = utcnow()
            self.repository.transition(job, "QUEUED")
        log_event("job_queued", job_id=str(job.id), project_id=str(project_id), status=job.status)
        return job, True

    @staticmethod
    def _equivalent(job: GenerationJob, digest: str):
        if job.request_fingerprint != digest:
            raise AppError(
                "Idempotency key was already used for a different request",
                "IDEMPOTENCY_CONFLICT",
                409,
            )
        return job

    def get(self, job_id: UUID):
        return self.repository.get(job_id)

    def list(self, project_id: UUID, limit: int, offset: int):
        ProjectRepository(self.session).get(project_id)
        return self.repository.list(project_id, limit, offset)

    def cancel(self, job_id: UUID):
        with self.session.begin():
            job = self.repository.get(job_id, lock=True)
            if job.status not in {"PENDING", "QUEUED"}:
                raise AppError(
                    "Only pending or queued jobs can be cancelled", "CANCELLATION_UNSUPPORTED", 409
                )
            job.finished_at = utcnow()
            self.repository.transition(job, "CANCELLED", "anonymous")
        return job

    def retry(self, job_id: UUID):
        with self.session.begin():
            job = self.repository.get(job_id, lock=True)
            if (
                job.status != "FAILED"
                or not job.metadata_json.get("retryable")
                or job.attempt_count >= job.max_attempts
            ):
                raise AppError("Job is not eligible for retry", "RETRY_NOT_ALLOWED", 409)
            job.queued_at = utcnow()
            job.available_at = utcnow()
            self.repository.transition(job, "QUEUED", "anonymous")
        return job
