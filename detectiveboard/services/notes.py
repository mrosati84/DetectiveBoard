"""Note persistence."""

from sqlalchemy import delete, insert, update
from sqlalchemy.orm import Session

from detectiveboard.database import row_to_dict
from detectiveboard.db import note_belongs_to_user
from detectiveboard.models import Note

# Returned/selected column order matches the previous raw-SQL NOTE_FIELDS.
NOTE_RETURNING = (Note.id, Note.content, Note.pos_x, Note.pos_y)

_UPDATABLE_NOTE_FIELDS = frozenset({"content", "pos_x", "pos_y"})


def note_is_owned(session: Session, note_id: int, user_id: int) -> bool:
    return note_belongs_to_user(session, note_id, user_id)


def create_note(
    session: Session,
    board_id: int,
    content: str,
    pos_x: float,
    pos_y: float,
) -> dict[str, object]:
    row = session.execute(
        insert(Note)
        .values(board_id=board_id, content=content, pos_x=pos_x, pos_y=pos_y)
        .returning(*NOTE_RETURNING)
    ).one()
    return row_to_dict(row)


def update_note(
    session: Session,
    note_id: int,
    updates: dict[str, object],
) -> dict[str, object]:
    clean = {
        key: value for key, value in updates.items() if key in _UPDATABLE_NOTE_FIELDS
    }
    if not clean:
        raise ValueError("Niente da aggiornare")
    row = session.execute(
        update(Note)
        .where(Note.id == note_id)
        .values(**clean)
        .returning(*NOTE_RETURNING)
    ).one()
    return row_to_dict(row)


def delete_note(session: Session, note_id: int) -> None:
    _ = session.execute(delete(Note).where(Note.id == note_id))
