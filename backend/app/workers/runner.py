import io
import json
import multiprocessing
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic
from uuid import UUID, uuid4

from sqlalchemy import select

from ..config import ROOT, Settings
from ..core.errors import AppError
from ..core.logging import log_event
from ..core.metrics import JOB_CLAIMS, JOB_DURATION, JOB_RETRIES, JOB_TIMEOUTS
from ..db.models import Artifact, Dataset, GenerationJob, Project
from ..db.repositories.jobs import JobClaim, QueueRepository, utcnow
from ..db.session import Database
from ..services.evaluation.inputs import verified_bytes
from ..services.generation.imaging import MODEL_FILES
from ..services.jobs.failures import JobFailure, classify_failure
from ..services.jobs.provenance import build_manifest
from ..storage.base import ArtifactStore
from ..storage.local import hash_stream
from .engine import generation_child


class Worker:
    def __init__(
        self,
        settings: Settings,
        database: Database,
        store: ArtifactStore,
        worker_id: str | None = None,
    ):
        self.settings = settings
        self.database = database
        self.store = store
        self.worker_id = worker_id or "worker-" + uuid4().hex
        self.queue = QueueRepository(database, settings.job_lease_seconds)

    def _compute(self, claim: JobClaim, dataset: Dataset | None, workspace: Path):
        source_path = None
        if dataset is not None:
            source_path = workspace / "source.csv"
            with self.store.get(dataset.storage_key) as source, source_path.open("wb") as target:
                shutil.copyfileobj(source, target, length=65536)
            with source_path.open("rb") as source:
                metadata = hash_stream(source)
            if metadata.sha256 != dataset.sha256 or metadata.size_bytes != dataset.size_bytes:
                raise AppError(
                    "Registered source integrity check failed",
                    "EVALUATION_SOURCE_INTEGRITY_FAILED"
                    if claim.job.job_kind == "EVALUATION"
                    else "SOURCE_ARTIFACT_INTEGRITY_FAILED"
                    if claim.job.modality == "tabular"
                    else "DATASET_INTEGRITY_FAILED",
                )
        spec = {
            "job_id": str(claim.job.id),
            "project_id": str(claim.job.project_id),
            "dataset_id": str(claim.job.dataset_id) if claim.job.dataset_id else None,
            "modality": claim.job.modality,
            "engine": claim.job.engine,
            "job_kind": claim.job.job_kind,
            "count": claim.job.requested_samples,
            "seed": claim.job.random_seed,
            "configuration": claim.job.configuration_json,
            "token": claim.job.claim_token.hex,
            "source_path": str(source_path) if source_path else None,
        }
        if claim.job.job_kind == "EVALUATION":
            descriptors = claim.job.configuration_json["inputs"]
            if dataset.sha256 != descriptors["source"]["sha256"]:
                raise AppError(
                    "Source reference changed since evaluation submission",
                    "EVALUATION_SOURCE_INTEGRITY_FAILED",
                )
            maximum = claim.job.configuration_json["limits"]["max_upload_mb"] * 1024**2
            with self.database.sessions() as session:
                for name, filename, error_code in (
                    ("synthetic", "synthetic.csv", "EVALUATION_SYNTHETIC_INTEGRITY_FAILED"),
                    (
                        "generation_manifest",
                        "generation_manifest.json",
                        "EVALUATION_MANIFEST_INVALID",
                    ),
                ):
                    descriptor = descriptors[name]
                    artifact = session.get(Artifact, UUID(descriptor["id"]))
                    artifact_job = session.get(GenerationJob, artifact.job_id) if artifact else None
                    if (
                        artifact is None
                        or artifact_job is None
                        or artifact_job.project_id != claim.job.project_id
                        or artifact.sha256 != descriptor["sha256"]
                        or artifact.size_bytes != descriptor["size_bytes"]
                    ):
                        raise AppError("Evaluation artifact reference changed", error_code)
                    raw = verified_bytes(
                        self.store,
                        artifact.storage_key,
                        descriptor["sha256"],
                        descriptor["size_bytes"],
                        error_code,
                        maximum,
                    )
                    path = workspace / filename
                    path.write_bytes(raw)
                    spec["synthetic_path" if name == "synthetic" else "manifest_path"] = str(path)
        context = multiprocessing.get_context("spawn")
        receive, send = context.Pipe(duplex=False)
        deadline = context.Value("d", monotonic() + self.settings.job_lease_seconds)
        child = context.Process(
            target=generation_child, args=(send, self.settings, spec, str(workspace), deadline)
        )
        child.start()
        send.close()
        next_heartbeat = monotonic() + self.settings.job_heartbeat_seconds
        timeout_at = monotonic() + claim.job.configuration_json.get("limits", {}).get(
            "evaluation_timeout_seconds"
            if claim.job.job_kind == "EVALUATION"
            else "tabular_job_timeout_seconds",
            self.settings.evaluation_timeout_seconds
            if claim.job.job_kind == "EVALUATION"
            else self.settings.tabular_job_timeout_seconds,
        )
        try:
            while True:
                if claim.job.modality == "tabular" and monotonic() >= timeout_at:
                    raise AppError(
                        "Evaluation exceeded the configured timeout"
                        if claim.job.job_kind == "EVALUATION"
                        else "Tabular training exceeded the configured job timeout",
                        "EVALUATION_TIMEOUT"
                        if claim.job.job_kind == "EVALUATION"
                        else "TABULAR_TRAINING_TIMEOUT",
                    )
                if receive.poll(0.1):
                    response = receive.recv()
                    if "event" in response:
                        self.queue.record_event(claim, response["event"])
                    else:
                        break
                if monotonic() >= next_heartbeat:
                    self.queue.heartbeat(claim)
                    deadline.value = monotonic() + self.settings.job_lease_seconds
                    next_heartbeat = monotonic() + self.settings.job_heartbeat_seconds
                if not child.is_alive():
                    if receive.poll(0.1):
                        continue
                    raise RuntimeError("Engine process exited without a result")
            child.join(timeout=10)
            if child.is_alive():
                raise RuntimeError("Engine process did not exit cleanly")
            self.queue.heartbeat(claim)
            if not response["ok"]:
                return JobFailure(**response["failure"])
            return response["result"]
        finally:
            # On lease/DB connection loss, stop computing before allowing recovery.
            if child.is_alive():
                child.terminate()
                child.join(timeout=10)
                if child.is_alive():
                    child.kill()
                    child.join(timeout=5)
            receive.close()

    def _publish(self, claim: JobClaim, dataset: Dataset | None, result: dict, workspace: Path):
        if claim.job.job_kind == "EVALUATION":
            return self._publish_evaluation(claim, result, workspace)
        token = claim.job.claim_token.hex
        outputs = workspace / "generated" / token
        sources = [
            (
                outputs / ("dataset.npz" if claim.job.modality == "timeseries" else "dataset.zip"),
                "SYNTHETIC_DATASET" if claim.job.modality == "timeseries" else "IMAGE_ARCHIVE",
                "application/octet-stream"
                if claim.job.modality == "timeseries"
                else "application/zip",
            )
        ]
        checkpoint = workspace / "models" / "trained" / token / "vae.pt"
        if claim.job.modality == "tabular":
            if not result["metadata"]["tabular"]["structural_validation"]["passed"]:
                raise AppError(
                    "Output structural validation failed", "TABULAR_STRUCTURAL_VALIDATION_FAILED"
                )
            sources = [
                (outputs / "dataset.csv", "SYNTHETIC_DATASET", "text/csv"),
                (outputs / "synthesizer.pkl", "SYNTHESIS_MODEL", "application/octet-stream"),
                (
                    outputs / "structural_validation.json",
                    "STRUCTURAL_VALIDATION_REPORT",
                    "application/json",
                ),
            ]
            model = {"identifier": claim.job.engine, "sha256": None}
        elif claim.job.modality == "timeseries":
            sources.append((checkpoint, "MODEL_CHECKPOINT", "application/octet-stream"))
            model = {"identifier": "pytorch-ecg-vae/full-checkpoint-v1", "sha256": None}
        else:
            pretrained = (
                self.settings.model_dir / MODEL_FILES[claim.job.configuration_json["modality"]]
            )
            model = {
                "identifier": pretrained.name,
                "sha256": result["metadata"]["source_schema_summary"]["checkpoint_sha256"],
            }
        records = []
        written = []
        try:
            for source, artifact_type, content_type in sources:
                artifact_id = uuid4()
                filename = "vae.pt" if artifact_type == "MODEL_CHECKPOINT" else source.name
                key = f"projects/{claim.job.project_id.hex}/jobs/{claim.job.id.hex}/attempts/{token}/{artifact_id.hex}/{filename}"
                with source.open("rb") as stream:
                    info = self.store.put(key, stream)
                written.append(key)
                if artifact_type in {"MODEL_CHECKPOINT", "SYNTHESIS_MODEL"}:
                    model["sha256"] = info.sha256
                    model["artifact_id"] = str(artifact_id)
                records.append(
                    Artifact(
                        id=artifact_id,
                        job_id=claim.job.id,
                        artifact_type=artifact_type,
                        filename=filename,
                        content_type=content_type,
                        size_bytes=info.size_bytes,
                        sha256=info.sha256,
                        storage_key=key,
                        metadata_json={
                            "attempt": claim.job.attempt_count,
                            "maturity": result["metadata"]["maturity"],
                            **(
                                {
                                    "engine": claim.job.engine,
                                    "engine_version": result["metadata"]["tabular"][
                                        "engine_version"
                                    ],
                                    "library_versions": result["metadata"]["tabular"][
                                        "library_versions"
                                    ],
                                    "model_sha256": info.sha256,
                                    "source_sha256": dataset.sha256,
                                    "metadata_hash": claim.job.configuration_json["metadata_hash"],
                                    "training_configuration": claim.job.configuration_json[
                                        "tabular"
                                    ],
                                    "split": claim.job.configuration_json["split"],
                                    "training_row_count": claim.job.configuration_json["split"][
                                        "training_row_count"
                                    ],
                                    "job_id": str(claim.job.id),
                                    "created_at": utcnow().isoformat(),
                                }
                                if artifact_type == "SYNTHESIS_MODEL"
                                else {}
                            ),
                        },
                    )
                )
            finished = utcnow()
            manifest = build_manifest(
                claim.job,
                dataset,
                result,
                [
                    {
                        "id": str(a.id),
                        "artifact_type": a.artifact_type,
                        "filename": a.filename,
                        "sha256": a.sha256,
                        "size_bytes": a.size_bytes,
                    }
                    for a in records
                ],
                model,
                finished,
                self.settings,
            )
            manifest_id = uuid4()
            manifest_key = f"projects/{claim.job.project_id.hex}/jobs/{claim.job.id.hex}/attempts/{token}/{manifest_id.hex}/run_manifest.json"
            info = self.store.put(manifest_key, io.BytesIO(json.dumps(manifest, indent=2).encode()))
            written.append(manifest_key)
            records.append(
                Artifact(
                    id=manifest_id,
                    job_id=claim.job.id,
                    artifact_type="RUN_METADATA",
                    filename="run_manifest.json",
                    content_type="application/json",
                    size_bytes=info.size_bytes,
                    sha256=info.sha256,
                    storage_key=manifest_key,
                    metadata_json={"manifest_version": 1},
                )
            )
            self.queue.heartbeat(claim)
            self.queue.succeed(
                claim, records, manifest, result["metadata"]["produced_sample_count"], finished
            )
        except Exception:
            # Reconcile an uncertain commit using a separate DB connection; never delete referenced bytes.
            try:
                with self.database.sessions() as session:
                    persisted = session.get(GenerationJob, claim.job.id)
                    if (
                        persisted
                        and persisted.status == "SUCCEEDED"
                        and persisted.claim_token == claim.job.claim_token
                    ):
                        return
                    referenced = set(
                        session.scalars(
                            select(Artifact.storage_key).where(Artifact.storage_key.in_(written))
                        )
                    )
                for key in written:
                    if key not in referenced:
                        self.store.delete(key)
            except Exception:
                log_event("orphan_reconciliation_required", job_id=str(claim.job.id))
            raise

    def _publish_evaluation(self, claim, result, workspace):
        token = claim.job.claim_token.hex
        outputs = workspace / "generated" / token
        records, written = [], []
        manifest = result["manifest"]
        try:
            for artifact_type in result["reports"] + ["EVALUATION_MANIFEST"]:
                artifact_id = uuid4()
                filename = artifact_type.lower() + ".json"
                if artifact_type == "EVALUATION_MANIFEST":
                    manifest["artifacts"] = [
                        {
                            "id": str(a.id),
                            "artifact_type": a.artifact_type,
                            "sha256": a.sha256,
                            "size_bytes": a.size_bytes,
                        }
                        for a in records
                    ]
                    (outputs / filename).write_text(
                        json.dumps(manifest, indent=2, allow_nan=False), encoding="utf-8"
                    )
                key = f"projects/{claim.job.project_id.hex}/evaluations/{claim.job.configuration_json['evaluation_run_id'].replace('-', '')}/attempts/{token}/{artifact_id.hex}/{filename}"
                with (outputs / filename).open("rb") as stream:
                    info = self.store.put(key, stream)
                written.append(key)
                records.append(
                    Artifact(
                        id=artifact_id,
                        job_id=claim.job.id,
                        artifact_type=artifact_type,
                        filename=filename,
                        content_type="application/json",
                        size_bytes=info.size_bytes,
                        sha256=info.sha256,
                        storage_key=key,
                        metadata_json={
                            "evaluation_run_id": claim.job.configuration_json["evaluation_run_id"],
                            "sensitive_internal": True,
                            "attempt": claim.job.attempt_count,
                        },
                    )
                )
            self.queue.heartbeat(claim)
            self.queue.succeed(claim, records, manifest, 1, utcnow())
        except Exception:
            # Same uncertain-commit discipline as generation: retain referenced bytes.
            try:
                with self.database.sessions() as session:
                    job = session.get(GenerationJob, claim.job.id)
                    if (
                        job
                        and job.status == "SUCCEEDED"
                        and job.claim_token == claim.job.claim_token
                    ):
                        return
                    referenced = set(
                        session.scalars(
                            select(Artifact.storage_key).where(Artifact.storage_key.in_(written))
                        )
                    )
                for key in written:
                    if key not in referenced:
                        self.store.delete(key)
            except Exception:
                log_event("orphan_reconciliation_required", job_id=str(claim.job.id))
            raise

    def run_once(self) -> bool:
        claim = self.queue.claim(self.worker_id)
        if claim is None:
            return False
        JOB_CLAIMS.inc()
        if claim.job.attempt_count > 1:
            JOB_RETRIES.inc()
        execution_start = monotonic()
        log_event(
            "job_claimed",
            job_id=str(claim.job.id),
            project_id=str(claim.job.project_id),
            worker_id=self.worker_id,
            attempt=claim.job.attempt_count,
        )
        work_root = ROOT / "backend/.work"
        work_root.mkdir(parents=True, exist_ok=True)
        try:
            with self.database.sessions() as session:
                dataset = (
                    session.get(Dataset, claim.job.dataset_id) if claim.job.dataset_id else None
                )
                project = session.get(Project, claim.job.project_id)
                if (
                    project is None
                    or project.deletion_state != "ACTIVE"
                    or (dataset is not None and dataset.project_id != project.id)
                ):
                    raise AppError("Work item ownership is invalid", "TENANT_INVARIANT_FAILED")
                log_event(
                    "job_ownership_verified",
                    job_id=str(claim.job.id),
                    organization_id=str(project.organization_id),
                )
            with TemporaryDirectory(prefix=f"job_{claim.job.id.hex}_", dir=work_root) as temporary:
                result = self._compute(claim, dataset, Path(temporary))
                if isinstance(result, JobFailure):
                    if result.code in {"EVALUATION_TIMEOUT", "TABULAR_TRAINING_TIMEOUT"}:
                        JOB_TIMEOUTS.inc()
                    self.queue.fail(
                        claim, result.code, result.message, result.retryable, result.diagnostics
                    )
                    log_event("job_failed", job_id=str(claim.job.id), error_code=result.code)
                else:
                    self._publish(claim, dataset, result, Path(temporary))
                    log_event("job_succeeded", job_id=str(claim.job.id), status="SUCCEEDED")
            return True
        except Exception as error:
            failure = classify_failure(error)
            if failure.code in {"EVALUATION_TIMEOUT", "TABULAR_TRAINING_TIMEOUT"}:
                JOB_TIMEOUTS.inc()
            if claim.job.job_kind == "EVALUATION" and failure.code == "GENERATION_FAILED":
                failure = JobFailure(
                    "EVALUATION_FAILED",
                    "Evaluation failed without publishing a completed report set",
                    False,
                )
            log_event(
                "worker_execution_failed",
                job_id=str(claim.job.id),
                error_code=failure.code,
                exception_type=type(error).__name__,
            )
            try:
                claim.connection.rollback()
                self.queue.fail(
                    claim, failure.code, failure.message, failure.retryable, failure.diagnostics
                )
            except Exception:
                log_event("job_recovery_required", job_id=str(claim.job.id))
            return True
        finally:
            try:
                JOB_DURATION.labels(claim.job.job_kind.lower()).observe(
                    monotonic() - execution_start
                )
                claim.release()
            except Exception:
                log_event("ownership_connection_closed", job_id=str(claim.job.id))
