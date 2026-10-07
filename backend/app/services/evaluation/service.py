import json
from importlib.metadata import PackageNotFoundError, version
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ...core.errors import AppError
from ...db.models import Artifact, Dataset, EvaluationRun, GenerationJob, ReleasePolicy
from ...db.repositories.catalog import AuditRepository, ProjectRepository, page
from ...db.repositories.jobs import JobRepository, utcnow
from ...schemas.evaluation import EvaluationRead, PolicyCreate
from ..tabular.profile import canonical_hash
from .inputs import validate_columns, validate_manifest, verified_bytes
from .policy import policy_hash

LIMIT_NAMES = (
    "evaluation_timeout_seconds",
    "dcr_max_rows",
    "disclosure_max_rows",
    "disclosure_estimate_rows",
    "disclosure_estimate_iterations",
    "quality_subsample_rows",
    "utility_max_rows",
    "utility_max_encoded_cells",
    "max_upload_mb",
    "tabular_max_source_rows",
    "tabular_max_columns",
)


def get_policy(session, policy_id):
    result = session.get(ReleasePolicy, policy_id)
    if result is None:
        raise AppError("Release policy does not exist", "RELEASE_POLICY_NOT_FOUND", 404)
    return result


def policy_snapshot(policy):
    return {
        "id": str(policy.id),
        "project_id": str(policy.project_id),
        "policy_hash": policy.policy_hash,
        **{key: getattr(policy, key) for key in PolicyCreate.model_fields},
    }


def evaluation_response(session, run, job=None):
    job = job if job is not None else session.get(GenerationJob, run.execution_job_id)
    data = {
        key: getattr(run, key)
        for key in (
            "id",
            "project_id",
            "dataset_id",
            "generation_job_id",
            "execution_job_id",
            "synthetic_artifact_id",
            "profile",
            "policy_id",
            "policy_version",
            "policy_hash",
            "configuration_json",
            "result_summary_json",
            "created_at",
        )
    }
    data.update(
        {
            key: getattr(job, key)
            for key in (
                "status",
                "queued_at",
                "started_at",
                "finished_at",
                "error_code",
                "error_message",
                "attempt_count",
                "worker_id",
            )
        }
    )
    return EvaluationRead.model_validate(data)


class EvaluationService:
    def __init__(self, session, settings, store):
        self.session, self.settings, self.store = session, settings, store

    def create_policy(self, project_id, request):
        try:
            with self.session.begin():
                ProjectRepository(self.session).get(project_id)
                policy = ReleasePolicy(
                    project_id=project_id,
                    **request.model_dump(mode="json"),
                    policy_hash=policy_hash(request.model_dump(mode="json")),
                )
                self.session.add(policy)
                self.session.flush()
                AuditRepository(self.session).record(
                    "RELEASE_POLICY_CREATED",
                    "release_policy",
                    policy.id,
                    metadata={"version": policy.version, "policy_hash": policy.policy_hash},
                )
            return policy
        except IntegrityError as error:
            raise AppError(
                "This policy name/version already exists", "RELEASE_POLICY_VERSION_EXISTS", 409
            ) from error

    def policies(self, project_id, limit, offset):
        ProjectRepository(self.session).get(project_id)
        return page(
            self.session,
            select(ReleasePolicy)
            .where(ReleasePolicy.project_id == project_id)
            .order_by(ReleasePolicy.created_at.desc()),
            limit,
            offset,
        )

    def submit(self, generation_id, request):
        try:
            compatible = version("sdmetrics") == "0.32.0" and version("scikit-learn") == "1.9.1"
        except PackageNotFoundError:
            compatible = False
        if not compatible:
            raise AppError(
                "Install the pinned supported evaluation runtime",
                "EVALUATION_ENGINE_UNAVAILABLE",
                501,
            )
        with self.session.begin():
            generation = JobRepository(self.session).get(generation_id)
            if (
                generation.status != "SUCCEEDED"
                or generation.modality != "tabular"
                or generation.job_kind != "GENERATION"
            ):
                raise AppError(
                    "Evaluation requires a successful tabular generation",
                    "EVALUATION_GENERATION_INELIGIBLE",
                )
            project = ProjectRepository(self.session).get(generation.project_id, shared_lock=True)
            if project.status != "ACTIVE":
                raise AppError("Project is archived", "PROJECT_ARCHIVED", 409)
            dataset = self.session.get(Dataset, generation.dataset_id)
            artifacts = list(
                self.session.scalars(select(Artifact).where(Artifact.job_id == generation.id))
            )
            try:
                synthetic = next(a for a in artifacts if a.artifact_type == "SYNTHETIC_DATASET")
                manifest_artifact = next(a for a in artifacts if a.artifact_type == "RUN_METADATA")
            except StopIteration as error:
                raise AppError(
                    "Required generation artifacts are absent", "EVALUATION_MANIFEST_INVALID"
                ) from error
            maximum = self.settings.max_upload_mb * 1024**2
            descriptors = {}
            raw_manifest = None
            for name, record, code in (
                ("source", dataset, "EVALUATION_SOURCE_INTEGRITY_FAILED"),
                ("synthetic", synthetic, "EVALUATION_SYNTHETIC_INTEGRITY_FAILED"),
                ("generation_manifest", manifest_artifact, "EVALUATION_MANIFEST_INVALID"),
            ):
                raw = verified_bytes(
                    self.store, record.storage_key, record.sha256, record.size_bytes, code, maximum
                )
                descriptors[name] = {
                    "id": str(record.id),
                    "sha256": record.sha256,
                    "size_bytes": record.size_bytes,
                }
                if name == "generation_manifest":
                    raw_manifest = raw
            try:
                manifest = json.loads(raw_manifest)
            except (ValueError, UnicodeError) as error:
                raise AppError(
                    "Generation manifest is invalid JSON", "EVALUATION_MANIFEST_INVALID"
                ) from error
            columns = validate_manifest(manifest, generation, dataset, synthetic)
            validate_columns(request, columns)
            policy = (
                get_policy(self.session, request.release_policy_id)
                if request.release_policy_id
                else None
            )
            if policy and policy.project_id != generation.project_id:
                raise AppError("Policy belongs to another project", "EVALUATION_POLICY_MISMATCH")
            snapshot = policy_snapshot(policy) if policy else None
            limits = {name: getattr(self.settings, name) for name in LIMIT_NAMES}
            run_id, execution_id = uuid4(), uuid4()
            configuration = {
                "request": request.model_dump(mode="json"),
                "inputs": descriptors,
                "generation_manifest_hash": canonical_hash(manifest),
                "policy": snapshot,
                "limits": limits,
                "evaluation_version": "1",
                "metadata_hash": manifest["tabular"]["metadata_hash"],
                "split": manifest["tabular"]["split"],
                "generation_engine": generation.engine,
            }
            execution = GenerationJob(
                id=execution_id,
                project_id=generation.project_id,
                dataset_id=dataset.id,
                modality="tabular",
                engine="evaluation-v1",
                job_kind="EVALUATION",
                status="PENDING",
                requested_samples=1,
                produced_samples=0,
                random_seed=request.random_seed,
                configuration_json={**configuration, "evaluation_run_id": str(run_id)},
                attempt_count=0,
                max_attempts=self.settings.job_max_attempts,
                metadata_json={},
                request_fingerprint=canonical_hash(configuration),
            )
            self.session.add(execution)
            self.session.flush()
            run = EvaluationRun(
                id=run_id,
                project_id=generation.project_id,
                dataset_id=dataset.id,
                generation_job_id=generation.id,
                execution_job_id=execution_id,
                synthetic_artifact_id=synthetic.id,
                profile=request.profile,
                policy_id=policy.id if policy else None,
                policy_version=policy.version if policy else None,
                policy_hash=policy.policy_hash if policy else None,
                configuration_json=configuration,
                result_summary_json={},
            )
            self.session.add(run)
            self.session.flush()
            execution.queued_at = utcnow()
            JobRepository(self.session).transition(execution, "QUEUED")
            AuditRepository(self.session).record(
                "EVALUATION_SUBMITTED",
                "evaluation",
                run.id,
                metadata={"generation_job_id": str(generation.id), "profile": request.profile},
            )
        return evaluation_response(self.session, run)

    def get(self, run_id):
        run = self.session.get(EvaluationRun, run_id)
        if run is None:
            raise AppError("Evaluation does not exist", "EVALUATION_NOT_FOUND", 404)
        return evaluation_response(self.session, run)

    def list(self, project_id, limit, offset):
        ProjectRepository(self.session).get(project_id)
        results = page(
            self.session,
            select(EvaluationRun)
            .where(EvaluationRun.project_id == project_id)
            .order_by(EvaluationRun.created_at.desc()),
            limit,
            offset,
        )
        jobs = {
            job.id: job
            for job in self.session.scalars(
                select(GenerationJob).where(
                    GenerationJob.id.in_([run.execution_job_id for run in results["items"]])
                )
            )
        }
        results["items"] = [
            evaluation_response(self.session, run, jobs[run.execution_job_id])
            for run in results["items"]
        ]
        return results

    def compare(self, project_id, ids):
        ProjectRepository(self.session).get(project_id)
        if len(set(ids)) != len(ids):
            raise AppError("Comparison IDs must be distinct", "EVALUATION_COMPARISON_INCOMPATIBLE")
        runs = [self.get(run_id) for run_id in ids]
        reference = None
        rows = []
        for run in runs:
            if run.project_id != project_id or run.status != "SUCCEEDED":
                raise AppError(
                    "Comparison requires successful evaluations in one project",
                    "EVALUATION_COMPARISON_INCOMPATIBLE",
                )
            cfg = run.configuration_json
            key = canonical_hash(
                {
                    "source": cfg["inputs"]["source"],
                    "metadata_hash": cfg["metadata_hash"],
                    "split": cfg["split"],
                    "request": cfg["request"],
                    "limits": cfg["limits"],
                    "policy_hash": run.policy_hash,
                }
            )
            if reference is not None and key != reference:
                raise AppError(
                    "Source, split, task, profile or policy configurations differ",
                    "EVALUATION_COMPARISON_INCOMPATIBLE",
                )
            reference = key
            rows.append(
                {
                    "evaluation_id": str(run.id),
                    "generation_job_id": str(run.generation_job_id),
                    "engine": cfg["generation_engine"],
                    "results": run.result_summary_json,
                }
            )
        return {
            "compatibility_hash": reference,
            "rows": rows,
            "interpretation": "Independent dimensions; input order preserved; no winner or composite ranking",
        }
