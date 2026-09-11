"""Card persistence."""

from sqlalchemy import delete, insert, update
from sqlalchemy.orm import Session

from detectiveboard.database import row_to_dict
from detectiveboard.db import card_belongs_to_user
from detectiveboard.models import Card

# Returned/selected column order matches the previous raw-SQL CARD_FIELDS.
CARD_RETURNING = (
    Card.id,
    Card.title,
    Card.description,
    Card.image_path,
    Card.pos_x,
    Card.pos_y,
    Card.pin_position,
    Card.inactive,
    Card.color,
)

_UPDATABLE_CARD_FIELDS = frozenset(
    {
        "title",
        "description",
        "pos_x",
        "pos_y",
        "pin_position",
        "inactive",
        "color",
        "image_path",
    }
)


def card_is_owned(session: Session, card_id: int, user_id: int) -> bool:
    return card_belongs_to_user(session, card_id, user_id)


def create_card(
    session: Session,
    board_id: int,
    title: str,
    description: str | None,
    pos_x: float,
    pos_y: float,
    pin_position: str,
    inactive: bool,
    color: str | None,
    image_path: str | None,
) -> dict[str, object]:
    row = session.execute(
        insert(Card)
        .values(
            board_id=board_id,
            title=title,
            description=description,
            image_path=image_path,
            pos_x=pos_x,
            pos_y=pos_y,
            pin_position=pin_position,
            inactive=inactive,
            color=color,
        )
        .returning(*CARD_RETURNING)
    ).one()
    return row_to_dict(row)


def update_card(
    session: Session,
    card_id: int,
    updates: dict[str, object],
) -> dict[str, object]:
    clean = {
        key: value for key, value in updates.items() if key in _UPDATABLE_CARD_FIELDS
    }
    if not clean:
        raise ValueError("Nothing to update")
    row = session.execute(
        update(Card)
        .where(Card.id == card_id)
        .values(**clean)
        .returning(*CARD_RETURNING)
    ).one()
    return row_to_dict(row)


def delete_card(session: Session, card_id: int) -> None:
    _ = session.execute(delete(Card).where(Card.id == card_id))


__all__ = [
    "CARD_RETURNING",
    "card_is_owned",
    "create_card",
    "delete_card",
    "update_card",
]
