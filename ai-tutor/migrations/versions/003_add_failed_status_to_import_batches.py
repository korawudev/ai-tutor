"""add failed status to import_batches

Revision ID: 003
Revises: 002
Create Date: 2026-09-04
"""
from alembic import op
import sqlalchemy as sa

revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None

def upgrade():
    op.drop_constraint('import_batches_status_check', 'import_batches', type_='check')
    op.execute(
        "ALTER TABLE import_batches ADD CONSTRAINT import_batches_status_check "
        "CHECK (status::text = ANY (ARRAY['processing'::character varying, "
        "'completed'::character varying, 'partial'::character varying, "
        "'failed'::character varying]::text[]))"
    )

def downgrade():
    op.drop_constraint('import_batches_status_check', 'import_batches', type_='check')
    op.execute(
        "ALTER TABLE import_batches ADD CONSTRAINT import_batches_status_check "
        "CHECK (status::text = ANY (ARRAY['processing'::character varying, "
        "'completed'::character varying, 'partial'::character varying]::text[]))"
    )
