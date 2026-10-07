"""Persistent platform schema

Revision ID: 0001_platform
Revises:
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_platform"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Frozen initial schema; deliberately independent of future ORM changes.
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("actor", sa.String(length=16), nullable=False),
        sa.Column(
            "metadata_json",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "actor IN ('anonymous','system','worker')", name=op.f("ck_audit_events_audit_actor")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_events")),
    )
    op.create_index(
        "ix_audit_entity_created",
        "audit_events",
        ["entity_type", "entity_id", "created_at"],
        unique=False,
    )
    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="ACTIVE", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE','ARCHIVED')", name=op.f("ck_projects_project_status")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_projects")),
    )
    op.create_table(
        "datasets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("modality", sa.String(length=16), nullable=False),
        sa.Column("original_filename", sa.String(length=240), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("column_count", sa.Integer(), nullable=False),
        sa.Column(
            "metadata_json",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "modality IN ('timeseries','tabular')", name=op.f("ck_datasets_dataset_modality")
        ),
        sa.CheckConstraint("status = 'READY'", name=op.f("ck_datasets_dataset_status")),
        sa.CheckConstraint("length(sha256) = 64", name=op.f("ck_datasets_dataset_hash")),
        sa.CheckConstraint(
            "size_bytes > 0 AND row_count > 0 AND column_count > 0",
            name=op.f("ck_datasets_dataset_size"),
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_datasets_project_id_projects"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_datasets")),
        sa.UniqueConstraint("id", "project_id", name="uq_datasets_id_project"),
        sa.UniqueConstraint("storage_key", name=op.f("uq_datasets_storage_key")),
    )
    op.create_index(
        "ix_datasets_project_created", "datasets", ["project_id", "created_at"], unique=False
    )
    op.create_index(op.f("ix_datasets_sha256"), "datasets", ["sha256"], unique=False)
    op.create_table(
        "generation_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=True),
        sa.Column("modality", sa.String(length=16), nullable=False),
        sa.Column("engine", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("requested_samples", sa.Integer(), nullable=False),
        sa.Column("produced_samples", sa.Integer(), nullable=False),
        sa.Column("random_seed", sa.BigInteger(), nullable=False),
        sa.Column(
            "configuration_json",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "available_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("claim_token", sa.Uuid(), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("worker_id", sa.String(length=120), nullable=True),
        sa.Column(
            "metadata_json",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.CheckConstraint(
            "(modality = 'timeseries' AND dataset_id IS NOT NULL) OR (modality = 'imaging' AND dataset_id IS NULL)",
            name=op.f("ck_generation_jobs_job_source"),
        ),
        sa.CheckConstraint(
            "modality IN ('timeseries','imaging')", name=op.f("ck_generation_jobs_job_modality")
        ),
        sa.CheckConstraint(
            "status != 'FAILED' OR (error_code IS NOT NULL AND error_message IS NOT NULL)",
            name=op.f("ck_generation_jobs_job_failure"),
        ),
        sa.CheckConstraint(
            "status != 'QUEUED' OR queued_at IS NOT NULL",
            name=op.f("ck_generation_jobs_job_queued"),
        ),
        sa.CheckConstraint(
            "status != 'RUNNING' OR (worker_id IS NOT NULL AND claim_token IS NOT NULL AND started_at IS NOT NULL AND lease_expires_at IS NOT NULL AND heartbeat_at IS NOT NULL)",
            name=op.f("ck_generation_jobs_job_running"),
        ),
        sa.CheckConstraint(
            "status != 'SUCCEEDED' OR produced_samples = requested_samples",
            name=op.f("ck_generation_jobs_job_success_count"),
        ),
        sa.CheckConstraint(
            "status IN ('PENDING','QUEUED','RUNNING','SUCCEEDED','FAILED','CANCELLED')",
            name=op.f("ck_generation_jobs_job_status"),
        ),
        sa.CheckConstraint(
            "status NOT IN ('SUCCEEDED','FAILED','CANCELLED') OR finished_at IS NOT NULL",
            name=op.f("ck_generation_jobs_job_terminal"),
        ),
        sa.CheckConstraint(
            "attempt_count >= 0 AND max_attempts BETWEEN 1 AND 5 AND attempt_count <= max_attempts",
            name=op.f("ck_generation_jobs_job_attempts"),
        ),
        sa.CheckConstraint(
            "random_seed >= 0 AND random_seed <= 4294967295",
            name=op.f("ck_generation_jobs_job_seed"),
        ),
        sa.CheckConstraint(
            "requested_samples > 0 AND produced_samples >= 0",
            name=op.f("ck_generation_jobs_job_counts"),
        ),
        sa.ForeignKeyConstraint(
            ["dataset_id", "project_id"],
            ["datasets.id", "datasets.project_id"],
            name="fk_job_dataset_project",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_generation_jobs_project_id_projects"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_generation_jobs")),
        sa.UniqueConstraint("project_id", "idempotency_key", name="uq_jobs_project_idempotency"),
    )
    op.create_index(
        "ix_jobs_project_created", "generation_jobs", ["project_id", "created_at"], unique=False
    )
    op.create_index(
        "ix_jobs_queue", "generation_jobs", ["status", "available_at", "created_at"], unique=False
    )
    op.create_table(
        "artifacts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("artifact_type", sa.String(length=32), nullable=False),
        sa.Column("filename", sa.String(length=240), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column(
            "metadata_json",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "artifact_type IN ('SYNTHETIC_DATASET','IMAGE_ARCHIVE','MODEL_CHECKPOINT','RUN_METADATA')",
            name=op.f("ck_artifacts_artifact_type"),
        ),
        sa.CheckConstraint(
            "size_bytes > 0 AND length(sha256) = 64", name=op.f("ck_artifacts_artifact_size_hash")
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["generation_jobs.id"],
            name=op.f("fk_artifacts_job_id_generation_jobs"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_artifacts")),
        sa.UniqueConstraint("storage_key", name=op.f("uq_artifacts_storage_key")),
    )
    op.create_index("ix_artifacts_job_created", "artifacts", ["job_id", "created_at"], unique=False)
    op.execute("""
        CREATE FUNCTION enforce_job_transition() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP = 'INSERT' THEN
            IF NEW.status <> 'PENDING' THEN
              RAISE EXCEPTION 'Job must begin pending' USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
          END IF;
          IF NEW.status = OLD.status THEN RETURN NEW; END IF;
          IF NOT (
            (OLD.status = 'PENDING' AND NEW.status IN ('QUEUED','CANCELLED')) OR
            (OLD.status = 'QUEUED' AND NEW.status IN ('RUNNING','CANCELLED')) OR
            (OLD.status = 'RUNNING' AND NEW.status IN ('SUCCEEDED','FAILED')) OR
            (OLD.status = 'FAILED' AND NEW.status = 'QUEUED')
          ) THEN
            RAISE EXCEPTION 'Illegal job state transition' USING ERRCODE = '23514';
          END IF;
          IF OLD.status = 'FAILED' AND NEW.status = 'QUEUED' AND
            (NEW.attempt_count >= NEW.max_attempts OR COALESCE((OLD.metadata_json->>'retryable')::boolean, false) = false) THEN
            RAISE EXCEPTION 'Retry is not permitted' USING ERRCODE = '23514';
          END IF;
          IF NEW.status = 'RUNNING' AND NEW.attempt_count <> OLD.attempt_count + 1 THEN
            RAISE EXCEPTION 'Attempt count must advance once' USING ERRCODE = '23514';
          END IF;
          RETURN NEW;
        END $$
    """)
    op.execute(
        "CREATE TRIGGER job_state_machine BEFORE INSERT OR UPDATE ON generation_jobs FOR EACH ROW EXECUTE FUNCTION enforce_job_transition()"
    )
    op.execute("""
        CREATE FUNCTION immutable_audit_event() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION 'Audit events are immutable' USING ERRCODE = '23514';
        END $$
    """)
    op.execute(
        "CREATE TRIGGER audit_immutable BEFORE UPDATE OR DELETE ON audit_events FOR EACH ROW EXECUTE FUNCTION immutable_audit_event()"
    )


def downgrade():
    op.execute("DROP TRIGGER job_state_machine ON generation_jobs")
    op.execute("DROP FUNCTION enforce_job_transition()")
    op.execute("DROP TRIGGER audit_immutable ON audit_events")
    op.execute("DROP FUNCTION immutable_audit_event()")
    op.drop_index("ix_artifacts_job_created", table_name="artifacts")
    op.drop_table("artifacts")
    op.drop_index("ix_jobs_queue", table_name="generation_jobs")
    op.drop_index("ix_jobs_project_created", table_name="generation_jobs")
    op.drop_table("generation_jobs")
    op.drop_index(op.f("ix_datasets_sha256"), table_name="datasets")
    op.drop_index("ix_datasets_project_created", table_name="datasets")
    op.drop_table("datasets")
    op.drop_table("projects")
    op.drop_index("ix_audit_entity_created", table_name="audit_events")
    op.drop_table("audit_events")
