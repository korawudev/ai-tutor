"""add review sm2 columns and verification_logs

Revision ID: 005
Revises: 004
Create Date: 2026-09-09
"""
from alembic import op
import sqlalchemy as sa

revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None

def upgrade():
    # review_schedule: 三分支 SM-2 新增字段
    op.add_column('review_schedule', sa.Column('correct_streak', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('review_schedule', sa.Column('last_normal_answer', sa.String(20), nullable=True))
    op.add_column('review_schedule', sa.Column('is_mastered', sa.Integer(), nullable=False, server_default='0'))

    # review_logs: 扩展日志字段
    op.add_column('review_logs', sa.Column('old_ease_factor', sa.Numeric(5, 2), nullable=True))
    op.add_column('review_logs', sa.Column('new_ease_factor', sa.Numeric(5, 2), nullable=True))
    op.add_column('review_logs', sa.Column('old_mastery_score', sa.Numeric(5, 2), nullable=True))
    op.add_column('review_logs', sa.Column('new_mastery_score', sa.Numeric(5, 2), nullable=True))
    op.add_column('review_logs', sa.Column('correct_streak', sa.Integer(), nullable=True))
    op.add_column('review_logs', sa.Column('answer_type', sa.String(20), nullable=True))
    op.add_column('review_logs', sa.Column('response_time_ms', sa.Integer(), nullable=True))

    # review_logs.result: 约束扩展为 3 分支 + 验证失败
    op.drop_constraint('review_logs_result_check', 'review_logs', type_='check')
    op.create_check_constraint(
        'review_logs_result_check',
        'review_logs',
        "result IN ('easy','good','hard','forgot','mastered','vague','forgotten','verification_failed')"
    )

    # verification_logs 表
    op.create_table(
        'verification_logs',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('chunk_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('chunks.id'), nullable=False),
        sa.Column('schedule_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('review_schedule.id'), nullable=True),
        sa.Column('verification_type', sa.String(20), nullable=False),
        sa.Column('user_answer', sa.Text(), nullable=True),
        sa.Column('ai_score', sa.Numeric(5, 2), nullable=True),
        sa.Column('passed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
    )

def downgrade():
    op.drop_table('verification_logs')
    op.drop_constraint('review_logs_result_check', 'review_logs', type_='check')
    op.create_check_constraint(
        'review_logs_result_check',
        'review_logs',
        "result IN ('easy','good','hard','forgot')"
    )
    op.drop_column('review_logs', 'response_time_ms')
    op.drop_column('review_logs', 'answer_type')
    op.drop_column('review_logs', 'correct_streak')
    op.drop_column('review_logs', 'new_mastery_score')
    op.drop_column('review_logs', 'old_mastery_score')
    op.drop_column('review_logs', 'new_ease_factor')
    op.drop_column('review_logs', 'old_ease_factor')
    op.drop_column('review_schedule', 'is_mastered')
    op.drop_column('review_schedule', 'last_normal_answer')
    op.drop_column('review_schedule', 'correct_streak')