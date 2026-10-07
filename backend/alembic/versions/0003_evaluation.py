"""Persistent evaluation domain and immutable project release policies.

Revision ID: 0003_evaluation
Revises: 0002_tabular
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0003_evaluation"
down_revision = "0002_tabular"
branch_labels = None
depends_on = None

GENERATION_TYPES = "'SYNTHETIC_DATASET','IMAGE_ARCHIVE','MODEL_CHECKPOINT','RUN_METADATA','SYNTHESIS_MODEL','STRUCTURAL_VALIDATION_REPORT'"
EVALUATION_TYPES = (
    "'QUALITY_REPORT','PRIVACY_REPORT','UTILITY_REPORT','RELEASE_DECISION','EVALUATION_MANIFEST'"
)


def column(name, kind, nullable=False, **kw):
    return sa.Column(name, kind, nullable=nullable, **kw)


def upgrade():
    op.add_column("generation_jobs", column("job_kind", sa.String(16), server_default="GENERATION"))
    op.create_check_constraint(
        "job_kind", "generation_jobs", "job_kind IN ('GENERATION','EVALUATION')"
    )
    op.create_check_constraint(
        "evaluation_work_item",
        "generation_jobs",
        "job_kind != 'EVALUATION' OR (modality='tabular' AND requested_samples=1 AND engine='evaluation-v1')",
    )
    op.drop_constraint(op.f("ck_artifacts_artifact_type"), "artifacts", type_="check")
    op.create_check_constraint(
        "artifact_type", "artifacts", f"artifact_type IN ({GENERATION_TYPES},{EVALUATION_TYPES})"
    )
    op.create_table(
        "release_policies",
        column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        column("name", sa.String(120)),
        column("version", sa.Integer()),
        column("description", sa.Text()),
        column("rules", JSONB()),
        column("illustrative", sa.Boolean()),
        column("policy_hash", sa.String(64)),
        column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "name", "version", name="uq_release_policy_version"),
        sa.UniqueConstraint("id", "project_id", name="uq_release_policy_project"),
        sa.CheckConstraint("version > 0 AND length(policy_hash) = 64", name="policy_version_hash"),
    )
    op.create_index("ix_policies_project_created", "release_policies", ["project_id", "created_at"])
    op.create_table(
        "evaluation_runs",
        column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        column("dataset_id", sa.Uuid()),
        sa.Column(
            "generation_job_id",
            sa.Uuid(),
            sa.ForeignKey("generation_jobs.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "execution_job_id",
            sa.Uuid(),
            sa.ForeignKey("generation_jobs.id", ondelete="RESTRICT"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "synthetic_artifact_id",
            sa.Uuid(),
            sa.ForeignKey("artifacts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        column("profile", sa.String(16)),
        column("policy_id", sa.Uuid(), True),
        column("policy_version", sa.Integer(), True),
        column("policy_hash", sa.String(64), True),
        column("configuration_json", JSONB()),
        column("result_summary_json", JSONB()),
        column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["dataset_id", "project_id"],
            ["datasets.id", "datasets.project_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["policy_id", "project_id"],
            ["release_policies.id", "release_policies.project_id"],
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("profile IN ('BASIC','STANDARD','FULL')", name="evaluation_profile"),
        sa.CheckConstraint(
            "(policy_id IS NULL AND policy_version IS NULL AND policy_hash IS NULL) OR (policy_id IS NOT NULL AND policy_version > 0 AND length(policy_hash)=64)",
            name="evaluation_policy",
        ),
    )
    op.create_index(
        "ix_evaluations_project_created", "evaluation_runs", ["project_id", "created_at"]
    )
    op.execute("""
      CREATE FUNCTION immutable_release_policy() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN RAISE EXCEPTION 'Policy versions are immutable; create a new version' USING ERRCODE='23514'; END $$
    """)
    op.execute(
        "CREATE TRIGGER release_policy_immutable BEFORE UPDATE OR DELETE ON release_policies FOR EACH ROW EXECUTE FUNCTION immutable_release_policy()"
    )
    op.execute("""
      CREATE FUNCTION validate_evaluation_references() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN
        IF TG_OP = 'UPDATE' AND (to_jsonb(NEW) - 'result_summary_json') IS DISTINCT FROM (to_jsonb(OLD) - 'result_summary_json') THEN
          RAISE EXCEPTION 'Evaluation configuration is immutable' USING ERRCODE='23514';
        END IF;
        IF NOT EXISTS (SELECT 1 FROM generation_jobs g JOIN generation_jobs e ON e.id=NEW.execution_job_id JOIN artifacts a ON a.id=NEW.synthetic_artifact_id
          WHERE g.id=NEW.generation_job_id AND g.job_kind='GENERATION' AND g.modality='tabular' AND g.status='SUCCEEDED'
          AND g.project_id=NEW.project_id AND g.dataset_id=NEW.dataset_id AND e.job_kind='EVALUATION'
          AND e.project_id=NEW.project_id AND e.dataset_id=NEW.dataset_id AND a.job_id=g.id AND a.artifact_type='SYNTHETIC_DATASET') THEN
          RAISE EXCEPTION 'Invalid evaluation references' USING ERRCODE='23514';
        END IF;
        IF NEW.policy_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM release_policies p WHERE p.id=NEW.policy_id AND p.version=NEW.policy_version AND p.policy_hash=NEW.policy_hash) THEN
          RAISE EXCEPTION 'Policy snapshot mismatch' USING ERRCODE='23514';
        END IF;
        RETURN NEW;
      END $$
    """)
    op.execute(
        "CREATE TRIGGER evaluation_references BEFORE INSERT OR UPDATE ON evaluation_runs FOR EACH ROW EXECUTE FUNCTION validate_evaluation_references()"
    )
    op.execute("""
      CREATE FUNCTION validate_evaluation_success() RETURNS trigger LANGUAGE plpgsql AS $$
      DECLARE r evaluation_runs%ROWTYPE;
      BEGIN
        IF NEW.job_kind='EVALUATION' AND NEW.status='SUCCEEDED' THEN
          SELECT * INTO r FROM evaluation_runs WHERE execution_job_id=NEW.id;
          IF r.id IS NULL OR r.result_summary_json = '{}'::jsonb OR
            (SELECT count(DISTINCT artifact_type) FROM artifacts WHERE job_id=NEW.id AND artifact_type IN ('QUALITY_REPORT','PRIVACY_REPORT','RELEASE_DECISION','EVALUATION_MANIFEST')) <> 4 OR
            (r.configuration_json->'request'->'utility' <> 'null'::jsonb AND NOT EXISTS(SELECT 1 FROM artifacts WHERE job_id=NEW.id AND artifact_type='UTILITY_REPORT')) THEN
            RAISE EXCEPTION 'Evaluation success requires complete published reports' USING ERRCODE='23514';
          END IF;
        END IF;
        RETURN NEW;
      END $$
    """)
    op.execute(
        "CREATE CONSTRAINT TRIGGER evaluation_success AFTER INSERT OR UPDATE ON generation_jobs DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION validate_evaluation_success()"
    )


def downgrade():
    if op.get_bind().scalar(
        sa.text(
            "SELECT EXISTS(SELECT 1 FROM evaluation_runs) OR EXISTS(SELECT 1 FROM release_policies) OR EXISTS(SELECT 1 FROM generation_jobs WHERE job_kind='EVALUATION')"
        )
    ):
        raise RuntimeError("Phase 4 records exist; downgrade refuses destructive removal")
    op.execute("DROP TRIGGER evaluation_success ON generation_jobs")
    op.execute("DROP FUNCTION validate_evaluation_success()")
    op.execute("DROP TRIGGER evaluation_references ON evaluation_runs")
    op.execute("DROP FUNCTION validate_evaluation_references()")
    op.execute("DROP TRIGGER release_policy_immutable ON release_policies")
    op.execute("DROP FUNCTION immutable_release_policy()")
    op.drop_table("evaluation_runs")
    op.drop_table("release_policies")
    op.drop_constraint(op.f("ck_artifacts_artifact_type"), "artifacts", type_="check")
    op.create_check_constraint(
        "artifact_type", "artifacts", f"artifact_type IN ({GENERATION_TYPES})"
    )
    op.drop_constraint(
        op.f("ck_generation_jobs_evaluation_work_item"), "generation_jobs", type_="check"
    )
    op.drop_constraint(op.f("ck_generation_jobs_job_kind"), "generation_jobs", type_="check")
    op.drop_column("generation_jobs", "job_kind")
