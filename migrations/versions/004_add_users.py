"""Add users table and user_id to boards

Revision ID: 004
Revises: 003
Create Date: 2026-02-21

"""
from alembic import op

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    op.execute("""
        ALTER TABLE boards ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id) ON DELETE CASCADE
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE boards DROP COLUMN IF EXISTS user_id")
    op.execute("DROP TABLE IF EXISTS users")
