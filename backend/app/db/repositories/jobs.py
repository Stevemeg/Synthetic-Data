import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import and_, func, or_, select, text, update
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from ...core.errors import AppError
from ...services.jobs.state import validate_transition
from ..models import Artifact, EvaluationRun, GenerationJob, Project
from ..session import Database
from .catalog import AuditRepository, page


def utcnow():
    return datetime.now(timezone.utc)


def lock_key(job_id: UUID) -> int:
    return int.from_bytes(hashlib.sha256(job_id.bytes).digest()[:8], "big", signed=True)


class JobRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(self, job_id: UUID, lock=False) -> GenerationJob:
        query = select(GenerationJob).where(GenerationJob.id == job_id)
        if lock:
            query = query.with_for_update()
        result = self.session.scalar(query)
        if result is None:
            raise AppError("Job does not exist", "JOB_NOT_FOUND", 404)
        return result

    def by_idempotency(self, project_id: UUID, key: str):
        return self.session.scalar(
            select(GenerationJob).where(
                GenerationJob.project_id == project_id, GenerationJob.idempotency_key == key
            )
        )

    def list(self, project_id: UUID, limit: int, offset: int):
        return page(
            self.session,
            select(GenerationJob)
            .where(GenerationJob.project_id == project_id, GenerationJob.job_kind == "GENERATION")
            .order_by(GenerationJob.created_at.desc(), GenerationJob.id),
            limit,
            offset,
        )

    def transition(self, job: GenerationJob, target: str, actor="system"):
        validate_transition(job.status, target)
        previous = job.status
        job.status = target
        AuditRepository(self.session).record(
            "JOB_TRANSITION",
            "job",
            job.id,
            actor,
            {"from": previous, "to": target, "attempt": job.attempt_count},
        )


@dataclass
class JobClaim:
    job: GenerationJob
    connection: Connection
    key: int

    def release(self):
        try:
            self.connection.rollback()
            self.connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": self.key})
            self.connection.commit()
        finally:
            # Do not put a connection with a session advisory lock back in the pool.
            self.connection.invalidate()
            self.connection.close()


class QueueRepository:
    """Atomic claims with row locks, session ownership locks, leases, and fencing."""

    def __init__(self, database: Database, lease_seconds: int):
        self.database = database
        self.lease_seconds = lease_seconds

    def claim(self, worker_id: str) -> JobClaim | None:
        connection = self.database.engine.connect()
        acquired_key = None
        try:
            with Session(bind=connection, expire_on_commit=False) as session, session.begin():
                candidates = list(
                    session.scalars(
                        select(GenerationJob)
                        .where(
                            GenerationJob.project_id.in_(
                                select(Project.id).where(Project.deletion_state == "ACTIVE")
                            ),
                            or_(
                                and_(
                                    GenerationJob.status == "QUEUED",
                                    GenerationJob.available_at <= func.now(),
                                ),
                                and_(
                                    GenerationJob.status == "RUNNING",
                                    GenerationJob.lease_expires_at < func.now(),
                                ),
                            ),
                        )
                        .order_by(GenerationJob.created_at, GenerationJob.id)
                        .limit(20)
                        .with_for_update(skip_locked=True)
                    )
                )
                for job in candidates:
                    key = lock_key(job.id)
                    if not session.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": key}):
                        continue
                    acquired_key = key
                    repository = JobRepository(session)
                    if job.status == "RUNNING":
                        job.finished_at = utcnow()
                        job.lease_expires_at = None
                        job.error_code = "WORKER_LOST"
                        job.error_message = "Previous worker ownership expired before completion"
                        job.metadata_json = {**job.metadata_json, "retryable": True}
                        repository.transition(job, "FAILED", "worker")
                        session.flush()
                        if job.attempt_count >= job.max_attempts:
                            session.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": key})
                            acquired_key = None
                            continue
                        repository.transition(job, "QUEUED", "worker")
                        job.queued_at = utcnow()
                        session.flush()
                    if job.attempt_count >= job.max_attempts:
                        raise RuntimeError("Queued job exhausted attempt budget")
                    now = utcnow()
                    job.attempt_count += 1
                    job.worker_id = worker_id
                    job.claim_token = uuid4()
                    job.started_at = now
                    job.finished_at = None
                    job.heartbeat_at = now
                    job.lease_expires_at = now + timedelta(seconds=self.lease_seconds)
                    job.error_code = None
                    job.error_message = None
                    repository.transition(job, "RUNNING", "worker")
                    if job.job_kind == "EVALUATION":
                        run_id = session.scalar(
                            select(EvaluationRun.id).where(EvaluationRun.execution_job_id == job.id)
                        )
                        AuditRepository(session).record(
                            "EVALUATION_STARTED",
                            "evaluation",
                            run_id,
                            "worker",
                            {"attempt": job.attempt_count},
                        )
                    session.flush()
                    session.expunge(job)
                    claim = JobClaim(job, connection, key)
                    break
                else:
                    claim = None
            if claim is None:
                connection.close()
            return claim
        except Exception:
            connection.rollback()
            if acquired_key is not None:
                connection.invalidate()
            connection.close()
            raise

    def heartbeat(self, claim: JobClaim):
        now = utcnow()
        with claim.connection.begin():
            result = claim.connection.execute(
                update(GenerationJob)
                .where(
                    GenerationJob.id == claim.job.id,
                    GenerationJob.status == "RUNNING",
                    GenerationJob.claim_token == claim.job.claim_token,
                    GenerationJob.worker_id == claim.job.worker_id,
                )
                .values(
                    heartbeat_at=now, lease_expires_at=now + timedelta(seconds=self.lease_seconds)
                )
            )
            if result.rowcount != 1:
                raise AppError("Worker no longer owns this job", "LEASE_LOST", 409)

    def owned(self, session: Session, claim: JobClaim) -> GenerationJob:
        job = JobRepository(session).get(claim.job.id, lock=True)
        if job.status != "RUNNING" or job.claim_token != claim.job.claim_token:
            raise AppError("Worker no longer owns this job", "LEASE_LOST", 409)
        return job

    def record_event(self, claim: JobClaim, event: str):
        if event not in {
            "TABULAR_TRAINING_STARTED",
            "TABULAR_SAMPLING_COMPLETED",
            "TABULAR_VALIDATION_COMPLETED",
            "QUALITY_EVALUATION_COMPLETED",
            "QUALITY_EVALUATION_STARTED",
            "PRIVACY_EVALUATION_COMPLETED",
            "UTILITY_EVALUATION_COMPLETED",
            "POLICY_EVALUATED",
        }:
            raise ValueError("Unknown worker event")
        with Session(bind=claim.connection) as session, session.begin():
            self.owned(session, claim)
            entity_id = claim.job.id
            entity_type = "job"
            if claim.job.job_kind == "EVALUATION":
                entity_id = session.scalar(
                    select(EvaluationRun.id).where(EvaluationRun.execution_job_id == claim.job.id)
                )
                entity_type = "evaluation"
            AuditRepository(session).record(
                event, entity_type, entity_id, "worker", {"attempt": claim.job.attempt_count}
            )

    def succeed(
        self,
        claim: JobClaim,
        artifacts: list[Artifact],
        metadata: dict,
        produced: int,
        finished_at: datetime,
    ):
        with Session(bind=claim.connection, expire_on_commit=False) as session, session.begin():
            job = self.owned(session, claim)
            if produced != job.requested_samples or not artifacts:
                raise AppError(
                    "Generation did not satisfy output contract", "GENERATION_CONTRACT_FAILED"
                )
            session.add_all(artifacts)
            job.produced_samples = produced
            job.metadata_json = metadata
            job.finished_at = finished_at
            job.lease_expires_at = None
            JobRepository(session).transition(job, "SUCCEEDED", "worker")
            if job.job_kind == "EVALUATION":
                run = session.scalar(
                    select(EvaluationRun)
                    .where(EvaluationRun.execution_job_id == job.id)
                    .with_for_update()
                )
                run.result_summary_json = metadata["metric_outputs"]
                AuditRepository(session).record(
                    "EVALUATION_SUCCEEDED",
                    "evaluation",
                    run.id,
                    "worker",
                    {"decision": run.result_summary_json["release"]["decision"]},
                )
            elif job.modality == "tabular":
                audit = AuditRepository(session)
                audit.record(
                    "TABULAR_MODEL_CREATED", "job", job.id, "worker", {"attempt": job.attempt_count}
                )
                audit.record(
                    "TABULAR_JOB_SUCCEEDED", "job", job.id, "worker", {"produced_rows": produced}
                )

    def fail(
        self,
        claim: JobClaim,
        code: str,
        message: str,
        retryable: bool,
        diagnostics: dict | None = None,
    ):
        with Session(bind=claim.connection, expire_on_commit=False) as session, session.begin():
            job = self.owned(session, claim)
            job.error_code = code
            job.error_message = message[:500]
            job.finished_at = utcnow()
            job.lease_expires_at = None
            job.metadata_json = {**job.metadata_json, "retryable": retryable, **(diagnostics or {})}
            repository = JobRepository(session)
            repository.transition(job, "FAILED", "worker")
            if job.job_kind == "EVALUATION":
                run_id = session.scalar(
                    select(EvaluationRun.id).where(EvaluationRun.execution_job_id == job.id)
                )
                AuditRepository(session).record(
                    "EVALUATION_FAILED",
                    "evaluation",
                    run_id,
                    "worker",
                    {"code": code, "attempt": job.attempt_count},
                )
            elif job.modality == "tabular":
                AuditRepository(session).record(
                    "TABULAR_JOB_FAILED",
                    "job",
                    job.id,
                    "worker",
                    {"code": code, "attempt": job.attempt_count},
                )
            session.flush()
            if retryable and job.attempt_count < job.max_attempts:
                repository.transition(job, "QUEUED", "worker")
                job.queued_at = utcnow()
                job.available_at = utcnow() + timedelta(seconds=min(2**job.attempt_count, 60))
