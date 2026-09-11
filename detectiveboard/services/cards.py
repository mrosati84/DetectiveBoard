"""Card persistence."""

import psycopg2.extras

from detectiveboard.db import card_belongs_to_user
from detectiveboard.services.columns import CARD_FIELDS, CARD_INSERT_COLUMNS


def card_is_owned(
    cur: psycopg2.extras.RealDictCursor, card_id: int, user_id: int
) -> bool:
    return card_belongs_to_user(card_id, user_id, cur)


def create_card(
    cur: psycopg2.extras.RealDictCursor,
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
    cur.execute(
        f"""
        INSERT INTO cards ({CARD_INSERT_COLUMNS})
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING {CARD_FIELDS}
        """,
        (
            board_id,
            title,
            description,
            image_path,
            pos_x,
            pos_y,
            pin_position,
            inactive,
            color,
        ),
    )
    row = cur.fetchone()
    assert row is not None
    return dict(row)


def update_card(
    cur: psycopg2.extras.RealDictCursor,
    card_id: int,
    updates: dict[str, object],
) -> dict[str, object]:
    fields = [f"{field} = %s" for field in updates]
    values: list[object] = [*updates.values(), card_id]
    cur.execute(
        f"UPDATE cards SET {', '.join(fields)} WHERE id = %s "
        + f"RETURNING {CARD_FIELDS}",
        values,
    )
    row = cur.fetchone()
    assert row is not None
    return dict(row)


def delete_card(cur: psycopg2.extras.RealDictCursor, card_id: int) -> None:
    cur.execute("DELETE FROM cards WHERE id = %s", (card_id,))
