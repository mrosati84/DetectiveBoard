"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-02-20

"""
from alembic import op

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS boards (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS cards (
            id SERIAL PRIMARY KEY,
            board_id INTEGER REFERENCES boards(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            description TEXT,
            image_path TEXT,
            pos_x FLOAT NOT NULL DEFAULT 100,
            pos_y FLOAT NOT NULL DEFAULT 100
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS connections (
            id SERIAL PRIMARY KEY,
            card_id_1 INTEGER REFERENCES cards(id) ON DELETE CASCADE,
            card_id_2 INTEGER REFERENCES cards(id) ON DELETE CASCADE,
            UNIQUE(card_id_1, card_id_2)
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS connections")
    op.execute("DROP TABLE IF EXISTS cards")
    op.execute("DROP TABLE IF EXISTS boards")
