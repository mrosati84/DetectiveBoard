"""Connection (red yarn) persistence."""

from sqlalchemy import delete, insert
from sqlalchemy.orm import Session

from detectiveboard.database import row_to_dict
from detectiveboard.db import card_belongs_to_user
from detectiveboard.models import Connection


def both_cards_owned(
    session: Session,
    user_id: int,
    card_id_1: int,
    card_id_2: int,
) -> bool:
    return card_belongs_to_user(session, card_id_1, user_id) and card_belongs_to_user(
        session, card_id_2, user_id
    )


def create_connection(
    session: Session, card_id_1: int, card_id_2: int
) -> dict[str, object]:
    row = session.execute(
        insert(Connection)
        .values(card_id_1=card_id_1, card_id_2=card_id_2)
        .returning(Connection.id, Connection.card_id_1, Connection.card_id_2)
    ).one()
    return row_to_dict(row)


def delete_connection(session: Session, card_id_1: int, card_id_2: int) -> None:
    _ = session.execute(
        delete(Connection).where(
            Connection.card_id_1 == card_id_1, Connection.card_id_2 == card_id_2
        )
    )
