"""Add share_token to boards

Revision ID: 005
Revises: 004
Create Date: 2026-02-22

"""
from alembic import op

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE boards ADD COLUMN IF NOT EXISTS share_token TEXT UNIQUE
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE boards DROP COLUMN IF EXISTS share_token")
