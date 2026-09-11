"""add deleted_at to chunks

Revision ID: 004
Revises: 003
Create Date: 2026-09-04
"""
from alembic import op
import sqlalchemy as sa

revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('chunks', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))

def downgrade():
    op.drop_column('chunks', 'deleted_at')
