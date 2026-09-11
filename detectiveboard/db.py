"""Database connection helpers and shared ownership queries."""

import os
from collections.abc import Generator
from contextlib import contextmanager

import psycopg2
import psycopg2.extensions
import psycopg2.extras


def get_db() -> psycopg2.extensions.connection:
    return psycopg2.connect(
        host=os.getenv("DATABASE_HOST", "localhost"),
        port=int(os.getenv("DATABASE_PORT", 5432)),
        user=os.getenv("DATABASE_USER", "postgres"),
        password=os.getenv("DATABASE_PASSWORD", "postgres"),
        dbname=os.getenv("DATABASE_NAME", "postgres"),
    )


@contextmanager
def db_cursor() -> Generator[psycopg2.extras.RealDictCursor, None, None]:
    """Yield a ``RealDictCursor`` and always close cursor/connection.

    Callers remain responsible for explicit ``commit``/``rollback`` via
    ``cur.connection``.
    """
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        yield cur
    finally:
        try:
            cur.close()
        finally:
            conn.close()


def board_belongs_to_user(
    board_id: int, user_id: int, cur: psycopg2.extras.RealDictCursor
) -> bool:
    cur.execute(
        "SELECT id FROM boards WHERE id = %s AND user_id = %s", (board_id, user_id)
    )
    return cur.fetchone() is not None


def card_belongs_to_user(
    card_id: int, user_id: int, cur: psycopg2.extras.RealDictCursor
) -> bool:
    cur.execute(
        "SELECT c.id FROM cards c JOIN boards b ON b.id = c.board_id WHERE c.id = %s AND b.user_id = %s",
        (card_id, user_id),
    )
    return cur.fetchone() is not None


def note_belongs_to_user(
    note_id: int, user_id: int, cur: psycopg2.extras.RealDictCursor
) -> bool:
    cur.execute(
        "SELECT n.id FROM notes n JOIN boards b ON b.id = n.board_id WHERE n.id = %s AND b.user_id = %s",
        (note_id, user_id),
    )
    return cur.fetchone() is not None
