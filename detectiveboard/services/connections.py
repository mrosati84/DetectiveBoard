"""Connection (red yarn) persistence."""

import psycopg2.extras

from detectiveboard.db import card_belongs_to_user


def both_cards_owned(
    cur: psycopg2.extras.RealDictCursor,
    user_id: int,
    card_id_1: int,
    card_id_2: int,
) -> bool:
    return card_belongs_to_user(card_id_1, user_id, cur) and card_belongs_to_user(
        card_id_2, user_id, cur
    )


def create_connection(
    cur: psycopg2.extras.RealDictCursor, card_id_1: int, card_id_2: int
) -> dict[str, object]:
    cur.execute(
        "INSERT INTO connections (card_id_1, card_id_2) VALUES (%s, %s) "
        + "RETURNING id, card_id_1, card_id_2",
        (card_id_1, card_id_2),
    )
    row = cur.fetchone()
    assert row is not None
    return dict(row)


def delete_connection(
    cur: psycopg2.extras.RealDictCursor, card_id_1: int, card_id_2: int
) -> None:
    cur.execute(
        "DELETE FROM connections WHERE card_id_1 = %s AND card_id_2 = %s",
        (card_id_1, card_id_2),
    )
