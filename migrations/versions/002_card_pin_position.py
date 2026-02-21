"""Add pin_position to cards

Revision ID: 002
Revises: 001
Create Date: 2026-02-21

"""
from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE cards ADD COLUMN IF NOT EXISTS pin_position TEXT NOT NULL DEFAULT 'center'
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE cards DROP COLUMN IF EXISTS pin_position")
