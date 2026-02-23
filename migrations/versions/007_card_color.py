"""Add color column to cards

Revision ID: 007
Revises: 006
Create Date: 2026-02-23

"""
from alembic import op

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE cards ADD COLUMN IF NOT EXISTS color TEXT
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE cards DROP COLUMN IF EXISTS color")
