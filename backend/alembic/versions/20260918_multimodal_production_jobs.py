"""Add durable multimodal production jobs.

Revision ID: multimodal_jobs_20260918
Revises: v4_0_growth_brain
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "multimodal_jobs_20260918"
down_revision = "v4_0_growth_brain"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "multimodal_production_jobs",
        sa.Column("job_id", sa.String(length=64), nullable=False),
        sa.Column("owner_id", sa.String(length=64), nullable=True),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("stage", sa.String(length=32), nullable=False),
        sa.Column("state_json", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("job_id"),
    )
    op.create_index(
        "ix_multimodal_production_jobs_owner_id",
        "multimodal_production_jobs",
        ["owner_id"],
        unique=False,
    )
    op.create_index(
        "ix_multimodal_production_jobs_platform",
        "multimodal_production_jobs",
        ["platform"],
        unique=False,
    )
    op.create_index(
        "ix_multimodal_production_jobs_status",
        "multimodal_production_jobs",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_multimodal_production_jobs_stage",
        "multimodal_production_jobs",
        ["stage"],
        unique=False,
    )
    op.create_index(
        "ix_multimodal_production_jobs_created_at",
        "multimodal_production_jobs",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_multimodal_production_jobs_updated_at",
        "multimodal_production_jobs",
        ["updated_at"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        "ix_multimodal_production_jobs_updated_at",
        table_name="multimodal_production_jobs",
    )
    op.drop_index(
        "ix_multimodal_production_jobs_created_at",
        table_name="multimodal_production_jobs",
    )
    op.drop_index(
        "ix_multimodal_production_jobs_stage",
        table_name="multimodal_production_jobs",
    )
    op.drop_index(
        "ix_multimodal_production_jobs_status",
        table_name="multimodal_production_jobs",
    )
    op.drop_index(
        "ix_multimodal_production_jobs_platform",
        table_name="multimodal_production_jobs",
    )
    op.drop_index(
        "ix_multimodal_production_jobs_owner_id",
        table_name="multimodal_production_jobs",
    )
    op.drop_table("multimodal_production_jobs")
