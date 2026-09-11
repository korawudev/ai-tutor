"""add review_batch_stats and nullable verification chunk_id

Revision ID: 006
Revises: 005
Create Date: 2026-09-09
"""

import sqlalchemy as sa
from alembic import op

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade():
    # verification_logs.chunk_id: 允许 NULL（feynman/manual 来源 schedule 无 chunk）
    op.alter_column(
        "verification_logs",
        "chunk_id",
        existing_type=sa.dialects.postgresql.UUID(as_uuid=True),
        nullable=True,
    )

    # review_batch_stats 表（基础埋点，v1.0 只写不读）
    op.create_table(
        "review_batch_stats",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("batch_id", sa.String(64), nullable=False),
        sa.Column("total_count", sa.Integer(), server_default="0"),
        sa.Column("mastered_count", sa.Integer(), server_default="0"),
        sa.Column("retry_count", sa.Integer(), server_default="0"),
        sa.Column("duration_sec", sa.Integer(), server_default="0"),
        sa.Column("avg_response_ms", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_review_batch_stats_user_id", "review_batch_stats", ["user_id"])
    op.create_index("ix_review_batch_stats_batch_id", "review_batch_stats", ["batch_id"])


def downgrade():
    op.drop_index("ix_review_batch_stats_batch_id", table_name="review_batch_stats")
    op.drop_index("ix_review_batch_stats_user_id", table_name="review_batch_stats")
    op.drop_table("review_batch_stats")
    op.alter_column(
        "verification_logs",
        "chunk_id",
        existing_type=sa.dialects.postgresql.UUID(as_uuid=True),
        nullable=False,
    )
