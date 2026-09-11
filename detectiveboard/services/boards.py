"""Board persistence and board payload assembly."""

from sqlalchemy import delete, insert, select, update
from sqlalchemy.orm import Session, aliased

from detectiveboard.database import row_to_dict
from detectiveboard.db import board_belongs_to_user
from detectiveboard.models import Board, Card, Connection, Note
from detectiveboard.services.cards import CARD_RETURNING
from detectiveboard.services.notes import NOTE_RETURNING


def board_is_owned(session: Session, board_id: int, user_id: int) -> bool:
    return board_belongs_to_user(session, board_id, user_id)


def list_boards(session: Session, user_id: int) -> list[dict[str, object]]:
    rows = session.execute(
        select(Board.id, Board.name, Board.created_at)
        .where(Board.user_id == user_id)
        .order_by(Board.created_at.desc())
    ).all()
    return [row_to_dict(row) for row in rows]


def create_board(session: Session, user_id: int, name: str) -> dict[str, object]:
    row = session.execute(
        insert(Board)
        .values(name=name, user_id=user_id)
        .returning(Board.id, Board.name, Board.created_at)
    ).one()
    return row_to_dict(row)


def board_contents(session: Session, board_id: int) -> dict[str, object]:
    card_rows = session.execute(
        select(*CARD_RETURNING).where(Card.board_id == board_id)
    ).all()
    cards = [row_to_dict(row) for row in card_rows]

    card_1 = aliased(Card)
    card_2 = aliased(Card)
    connection_rows = session.execute(
        select(Connection.id, Connection.card_id_1, Connection.card_id_2)
        .select_from(Connection)
        .join(card_1, card_1.id == Connection.card_id_1)
        .join(card_2, card_2.id == Connection.card_id_2)
        .where(card_1.board_id == board_id, card_2.board_id == board_id)
    ).all()
    connections = [row_to_dict(row) for row in connection_rows]

    note_rows = session.execute(
        select(*NOTE_RETURNING).where(Note.board_id == board_id)
    ).all()
    notes = [row_to_dict(row) for row in note_rows]

    return {"cards": cards, "connections": connections, "notes": notes}


def get_board(
    session: Session, board_id: int, user_id: int
) -> dict[str, object] | None:
    row = session.execute(
        select(Board.id, Board.name, Board.share_token).where(
            Board.id == board_id, Board.user_id == user_id
        )
    ).first()
    if row is None:
        return None
    return {"board": row_to_dict(row), **board_contents(session, board_id)}


def rename_board(
    session: Session, board_id: int, user_id: int, name: str
) -> dict[str, object] | None:
    row = session.execute(
        update(Board)
        .where(Board.id == board_id, Board.user_id == user_id)
        .values(name=name)
        .returning(Board.id, Board.name)
    ).first()
    if row is None:
        return None
    return row_to_dict(row)


def delete_board(session: Session, board_id: int, user_id: int) -> None:
    _ = session.execute(
        delete(Board).where(Board.id == board_id, Board.user_id == user_id)
    )
