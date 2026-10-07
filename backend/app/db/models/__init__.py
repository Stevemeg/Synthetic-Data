"""Explicit platform entities; raw healthcare records are never stored here."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base

JSON_TYPE = JSON().with_variant(JSONB(), "postgresql")
DEFAULT_ORGANIZATION_ID = UUID("00000000-0000-4000-8000-000000000001")


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("issuer", "subject", name="uq_users_external_identity"),
        CheckConstraint("status IN ('ACTIVE','DISABLED')", name="user_status"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    issuer: Mapped[str] = mapped_column(String(512))
    subject: Mapped[str] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(320))
    display_name: Mapped[str] = mapped_column(String(120), default="")
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE", server_default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Organization(Base):
    __tablename__ = "organizations"
    __table_args__ = (
        CheckConstraint("status IN ('ACTIVE','DISABLED')", name="organization_status"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(120), unique=True)
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE", server_default="ACTIVE")
    retention_policy: Mapped[dict] = mapped_column(
        JSON_TYPE,
        default=lambda: {
            "source": "manual",
            "synthetic": "manual",
            "model": "manual",
            "report": "manual",
        },
        server_default='{"source":"manual","synthetic":"manual","model":"manual","report":"manual"}',
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OrganizationMembership(Base):
    __tablename__ = "organization_memberships"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_membership_org_user"),
        CheckConstraint("role IN ('OWNER','EDITOR','VIEWER')", name="membership_role"),
        CheckConstraint("status IN ('ACTIVE','REMOVED')", name="membership_status"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), index=True
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    role: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE", server_default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LoginSession(Base):
    __tablename__ = "login_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    csrf_token: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint("status IN ('ACTIVE','ARCHIVED')", name="project_status"),
        CheckConstraint(
            "deletion_state IN ('ACTIVE','DELETION_REQUESTED','PURGING','DELETED')",
            name="project_deletion_state",
        ),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        default=DEFAULT_ORGANIZATION_ID,
        server_default=str(DEFAULT_ORGANIZATION_ID),
        index=True,
    )
    deletion_state: Mapped[str] = mapped_column(
        String(24), default="ACTIVE", server_default="ACTIVE"
    )
    deletion_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    purged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE", server_default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Dataset(Base):
    __tablename__ = "datasets"
    __table_args__ = (
        UniqueConstraint("id", "project_id", name="uq_datasets_id_project"),
        CheckConstraint("status = 'READY'", name="dataset_status"),
        CheckConstraint("modality IN ('timeseries','tabular')", name="dataset_modality"),
        CheckConstraint(
            "size_bytes > 0 AND row_count > 0 AND column_count > 0", name="dataset_size"
        ),
        CheckConstraint("length(sha256) = 64", name="dataset_hash"),
        Index("ix_datasets_project_created", "project_id", "created_at"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"))
    name: Mapped[str] = mapped_column(String(120))
    modality: Mapped[str] = mapped_column(String(16))
    original_filename: Mapped[str] = mapped_column(String(240))
    content_type: Mapped[str] = mapped_column(String(120))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    storage_key: Mapped[str] = mapped_column(String(512), unique=True)
    status: Mapped[str] = mapped_column(String(16), default="READY")
    row_count: Mapped[int] = mapped_column(Integer)
    column_count: Mapped[int] = mapped_column(Integer)
    metadata_json: Mapped[dict] = mapped_column(JSON_TYPE, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GenerationJob(Base):
    __tablename__ = "generation_jobs"
    __table_args__ = (
        CheckConstraint("job_kind IN ('GENERATION','EVALUATION')", name="job_kind"),
        CheckConstraint(
            "job_kind != 'EVALUATION' OR (modality = 'tabular' AND requested_samples = 1 AND engine = 'evaluation-v1')",
            name="evaluation_work_item",
        ),
        ForeignKeyConstraint(
            ["dataset_id", "project_id"],
            ["datasets.id", "datasets.project_id"],
            ondelete="RESTRICT",
            name="fk_job_dataset_project",
        ),
        UniqueConstraint("project_id", "idempotency_key", name="uq_jobs_project_idempotency"),
        CheckConstraint(
            "status IN ('PENDING','QUEUED','RUNNING','SUCCEEDED','FAILED','CANCELLED')",
            name="job_status",
        ),
        CheckConstraint("modality IN ('timeseries','imaging','tabular')", name="job_modality"),
        CheckConstraint(
            "(modality IN ('timeseries','tabular') AND dataset_id IS NOT NULL) OR (modality = 'imaging' AND dataset_id IS NULL)",
            name="job_source",
        ),
        CheckConstraint("requested_samples > 0 AND produced_samples >= 0", name="job_counts"),
        CheckConstraint("random_seed >= 0 AND random_seed <= 4294967295", name="job_seed"),
        CheckConstraint(
            "attempt_count >= 0 AND max_attempts BETWEEN 1 AND 5 AND attempt_count <= max_attempts",
            name="job_attempts",
        ),
        CheckConstraint("status != 'QUEUED' OR queued_at IS NOT NULL", name="job_queued"),
        CheckConstraint(
            "status != 'RUNNING' OR (worker_id IS NOT NULL AND claim_token IS NOT NULL AND started_at IS NOT NULL AND lease_expires_at IS NOT NULL AND heartbeat_at IS NOT NULL)",
            name="job_running",
        ),
        CheckConstraint(
            "status NOT IN ('SUCCEEDED','FAILED','CANCELLED') OR finished_at IS NOT NULL",
            name="job_terminal",
        ),
        CheckConstraint(
            "status != 'SUCCEEDED' OR produced_samples = requested_samples",
            name="job_success_count",
        ),
        CheckConstraint(
            "status != 'FAILED' OR (error_code IS NOT NULL AND error_message IS NOT NULL)",
            name="job_failure",
        ),
        Index("ix_jobs_queue", "status", "available_at", "created_at"),
        Index("ix_jobs_project_created", "project_id", "created_at"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"))
    dataset_id: Mapped[UUID | None] = mapped_column(Uuid)
    modality: Mapped[str] = mapped_column(String(16))
    engine: Mapped[str] = mapped_column(String(64))
    job_kind: Mapped[str] = mapped_column(
        String(16), default="GENERATION", server_default="GENERATION"
    )
    status: Mapped[str] = mapped_column(String(16), default="PENDING")
    requested_samples: Mapped[int] = mapped_column(Integer)
    produced_samples: Mapped[int] = mapped_column(Integer, default=0)
    random_seed: Mapped[int] = mapped_column(BigInteger)
    configuration_json: Mapped[dict] = mapped_column(JSON_TYPE)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    claim_token: Mapped[UUID | None] = mapped_column(Uuid)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(String(500))
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer)
    worker_id: Mapped[str | None] = mapped_column(String(120))
    metadata_json: Mapped[dict] = mapped_column(JSON_TYPE, default=dict)
    idempotency_key: Mapped[str | None] = mapped_column(String(128))
    request_fingerprint: Mapped[str] = mapped_column(String(64))


class Artifact(Base):
    __tablename__ = "artifacts"
    __table_args__ = (
        CheckConstraint(
            "artifact_type IN ('SYNTHETIC_DATASET','IMAGE_ARCHIVE','MODEL_CHECKPOINT','RUN_METADATA','SYNTHESIS_MODEL','STRUCTURAL_VALIDATION_REPORT','QUALITY_REPORT','PRIVACY_REPORT','UTILITY_REPORT','RELEASE_DECISION','EVALUATION_MANIFEST','GOVERNANCE_REPORT')",
            name="artifact_type",
        ),
        CheckConstraint("size_bytes > 0 AND length(sha256) = 64", name="artifact_size_hash"),
        Index("ix_artifacts_job_created", "job_id", "created_at"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(ForeignKey("generation_jobs.id", ondelete="RESTRICT"))
    artifact_type: Mapped[str] = mapped_column(String(32))
    filename: Mapped[str] = mapped_column(String(240))
    content_type: Mapped[str] = mapped_column(String(120))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    storage_key: Mapped[str] = mapped_column(String(512), unique=True)
    metadata_json: Mapped[dict] = mapped_column(JSON_TYPE, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReleasePolicy(Base):
    __tablename__ = "release_policies"
    __table_args__ = (
        UniqueConstraint("project_id", "name", "version", name="uq_release_policy_version"),
        UniqueConstraint("id", "project_id", name="uq_release_policy_project"),
        CheckConstraint("version > 0 AND length(policy_hash) = 64", name="policy_version_hash"),
        Index("ix_policies_project_created", "project_id", "created_at"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"))
    name: Mapped[str] = mapped_column(String(120))
    version: Mapped[int] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(Text, default="")
    rules: Mapped[dict] = mapped_column(JSON_TYPE)
    illustrative: Mapped[bool] = mapped_column(Boolean, default=False)
    policy_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EvaluationRun(Base):
    """Domain/results separate from its execution item in the existing queue."""

    __tablename__ = "evaluation_runs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["dataset_id", "project_id"],
            ["datasets.id", "datasets.project_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["policy_id", "project_id"],
            ["release_policies.id", "release_policies.project_id"],
            ondelete="RESTRICT",
        ),
        CheckConstraint("profile IN ('BASIC','STANDARD','FULL')", name="evaluation_profile"),
        CheckConstraint(
            "(policy_id IS NULL AND policy_version IS NULL AND policy_hash IS NULL) OR (policy_id IS NOT NULL AND policy_version > 0 AND length(policy_hash)=64)",
            name="evaluation_policy",
        ),
        Index("ix_evaluations_project_created", "project_id", "created_at"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"))
    dataset_id: Mapped[UUID] = mapped_column(Uuid)
    generation_job_id: Mapped[UUID] = mapped_column(
        ForeignKey("generation_jobs.id", ondelete="RESTRICT")
    )
    execution_job_id: Mapped[UUID] = mapped_column(
        ForeignKey("generation_jobs.id", ondelete="RESTRICT"), unique=True
    )
    synthetic_artifact_id: Mapped[UUID] = mapped_column(
        ForeignKey("artifacts.id", ondelete="RESTRICT")
    )
    profile: Mapped[str] = mapped_column(String(16))
    policy_id: Mapped[UUID | None] = mapped_column(Uuid)
    policy_version: Mapped[int | None] = mapped_column(Integer)
    policy_hash: Mapped[str | None] = mapped_column(String(64))
    configuration_json: Mapped[dict] = mapped_column(JSON_TYPE)
    result_summary_json: Mapped[dict] = mapped_column(JSON_TYPE, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        CheckConstraint("actor IN ('anonymous','system','worker','user')", name="audit_actor"),
        Index("ix_audit_entity_created", "entity_type", "entity_id", "created_at"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    event_type: Mapped[str] = mapped_column(String(64))
    entity_type: Mapped[str] = mapped_column(String(32))
    entity_id: Mapped[UUID] = mapped_column(Uuid)
    actor: Mapped[str] = mapped_column(String(16))
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    organization_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), index=True
    )
    request_id: Mapped[str | None] = mapped_column(String(64))
    metadata_json: Mapped[dict] = mapped_column(JSON_TYPE, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
