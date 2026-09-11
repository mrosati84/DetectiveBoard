"""Note persistence."""

import psycopg2.extras

from detectiveboard.db import note_belongs_to_user
from detectiveboard.services.columns import NOTE_FIELDS


def note_is_owned(
    cur: psycopg2.extras.RealDictCursor, note_id: int, user_id: int
) -> bool:
    return note_belongs_to_user(note_id, user_id, cur)


def create_note(
    cur: psycopg2.extras.RealDictCursor,
    board_id: int,
    content: str,
    pos_x: float,
    pos_y: float,
) -> dict[str, object]:
    cur.execute(
        "INSERT INTO notes (board_id, content, pos_x, pos_y) VALUES (%s, %s, %s, %s) "
        + f"RETURNING {NOTE_FIELDS}",
        (board_id, content, pos_x, pos_y),
    )
    row = cur.fetchone()
    assert row is not None
    return dict(row)


def update_note(
    cur: psycopg2.extras.RealDictCursor,
    note_id: int,
    updates: dict[str, object],
) -> dict[str, object]:
    fields = [f"{field} = %s" for field in updates]
    values: list[object] = [*updates.values(), note_id]
    cur.execute(
        f"UPDATE notes SET {', '.join(fields)} WHERE id = %s "
        + f"RETURNING {NOTE_FIELDS}",
        values,
    )
    row = cur.fetchone()
    assert row is not None
    return dict(row)


def delete_note(cur: psycopg2.extras.RealDictCursor, note_id: int) -> None:
    cur.execute("DELETE FROM notes WHERE id = %s", (note_id,))
