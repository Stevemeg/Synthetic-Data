"""Enable tabular jobs and restricted model / structural report artifacts.

Revision ID: 0002_tabular
Revises: 0001_platform
"""

import sqlalchemy as sa
from alembic import op

revision = "0002_tabular"
down_revision = "0001_platform"
branch_labels = None
depends_on = None


def constraints(tabular: bool):
    for table, name in (
        ("generation_jobs", "job_modality"),
        ("generation_jobs", "job_source"),
        ("artifacts", "artifact_type"),
    ):
        op.drop_constraint(op.f(f"ck_{table}_{name}"), table, type_="check")
    op.create_check_constraint(
        "job_modality",
        "generation_jobs",
        "modality IN ('timeseries','imaging','tabular')"
        if tabular
        else "modality IN ('timeseries','imaging')",
    )
    op.create_check_constraint(
        "job_source",
        "generation_jobs",
        "(modality IN ('timeseries','tabular') AND dataset_id IS NOT NULL) OR (modality = 'imaging' AND dataset_id IS NULL)"
        if tabular
        else "(modality = 'timeseries' AND dataset_id IS NOT NULL) OR (modality = 'imaging' AND dataset_id IS NULL)",
    )
    op.create_check_constraint(
        "artifact_type",
        "artifacts",
        "artifact_type IN ('SYNTHETIC_DATASET','IMAGE_ARCHIVE','MODEL_CHECKPOINT','RUN_METADATA','SYNTHESIS_MODEL','STRUCTURAL_VALIDATION_REPORT')"
        if tabular
        else "artifact_type IN ('SYNTHETIC_DATASET','IMAGE_ARCHIVE','MODEL_CHECKPOINT','RUN_METADATA')",
    )


def upgrade():
    constraints(True)


def downgrade():
    # Refuse rather than destroy tabular records or established ECG/imaging data.
    if op.get_bind().scalar(
        sa.text(
            "SELECT EXISTS(SELECT 1 FROM generation_jobs WHERE modality='tabular') OR EXISTS(SELECT 1 FROM artifacts WHERE artifact_type IN ('SYNTHESIS_MODEL','STRUCTURAL_VALIDATION_REPORT'))"
        )
    ):
        raise RuntimeError("Phase 3 records exist; downgrade is only supported before tabular use")
    constraints(False)
