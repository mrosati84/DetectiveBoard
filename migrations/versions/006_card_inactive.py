"""Add inactive column to cards

Revision ID: 006
Revises: 005
Create Date: 2026-02-23

"""
from alembic import op

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE cards ADD COLUMN IF NOT EXISTS inactive BOOLEAN NOT NULL DEFAULT FALSE
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE cards DROP COLUMN IF EXISTS inactive")
