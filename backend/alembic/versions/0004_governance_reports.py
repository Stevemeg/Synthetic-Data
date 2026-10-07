"""Registered internal HTML governance reports.

Revision ID: 0004_governance_reports
Revises: 0003_evaluation
"""

import sqlalchemy as sa
from alembic import op

revision = "0004_governance_reports"
down_revision = "0003_evaluation"
branch_labels = None
depends_on = None
TYPES = "'SYNTHETIC_DATASET','IMAGE_ARCHIVE','MODEL_CHECKPOINT','RUN_METADATA','SYNTHESIS_MODEL','STRUCTURAL_VALIDATION_REPORT','QUALITY_REPORT','PRIVACY_REPORT','UTILITY_REPORT','RELEASE_DECISION','EVALUATION_MANIFEST'"


def upgrade():
    op.drop_constraint(op.f("ck_artifacts_artifact_type"), "artifacts", type_="check")
    op.create_check_constraint(
        "artifact_type", "artifacts", f"artifact_type IN ({TYPES},'GOVERNANCE_REPORT')"
    )


def downgrade():
    if op.get_bind().scalar(
        sa.text("SELECT count(*) FROM artifacts WHERE artifact_type='GOVERNANCE_REPORT'")
    ):
        raise RuntimeError("Cannot downgrade while governance reports exist")
    op.drop_constraint(op.f("ck_artifacts_artifact_type"), "artifacts", type_="check")
    op.create_check_constraint("artifact_type", "artifacts", f"artifact_type IN ({TYPES})")
