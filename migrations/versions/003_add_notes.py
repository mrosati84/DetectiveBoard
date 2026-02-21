"""Add notes table

Revision ID: 003
Revises: 002
Create Date: 2026-02-21

"""
from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id SERIAL PRIMARY KEY,
            board_id INTEGER REFERENCES boards(id) ON DELETE CASCADE,
            content TEXT NOT NULL DEFAULT '',
            pos_x FLOAT NOT NULL DEFAULT 100,
            pos_y FLOAT NOT NULL DEFAULT 100
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS notes")
