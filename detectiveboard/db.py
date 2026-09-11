"""Database session helpers and shared ownership queries."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from detectiveboard.models import Board, Card, Note


def board_belongs_to_user(session: Session, board_id: int, user_id: int) -> bool:
    return (
        session.execute(
            select(Board.id).where(Board.id == board_id, Board.user_id == user_id)
        ).first()
        is not None
    )


def card_belongs_to_user(session: Session, card_id: int, user_id: int) -> bool:
    return (
        session.execute(
            select(Card.id)
            .join(Board, Board.id == Card.board_id)
            .where(Card.id == card_id, Board.user_id == user_id)
        ).first()
        is not None
    )


def note_belongs_to_user(session: Session, note_id: int, user_id: int) -> bool:
    return (
        session.execute(
            select(Note.id)
            .join(Board, Board.id == Note.board_id)
            .where(Note.id == note_id, Board.user_id == user_id)
        ).first()
        is not None
    )
