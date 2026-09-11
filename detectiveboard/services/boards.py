"""Board persistence and board payload assembly."""

import psycopg2.extras

from detectiveboard.db import board_belongs_to_user
from detectiveboard.services.columns import CARD_FIELDS, NOTE_FIELDS


def board_is_owned(
    cur: psycopg2.extras.RealDictCursor, board_id: int, user_id: int
) -> bool:
    return board_belongs_to_user(board_id, user_id, cur)


def list_boards(
    cur: psycopg2.extras.RealDictCursor, user_id: int
) -> list[dict[str, object]]:
    cur.execute(
        "SELECT id, name, created_at FROM boards WHERE user_id = %s ORDER BY created_at DESC",
        (user_id,),
    )
    return [dict(b) for b in cur.fetchall()]


def create_board(
    cur: psycopg2.extras.RealDictCursor, user_id: int, name: str
) -> dict[str, object]:
    cur.execute(
        "INSERT INTO boards (name, user_id) VALUES (%s, %s) RETURNING id, name, created_at",
        (name, user_id),
    )
    row = cur.fetchone()
    assert row is not None
    return dict(row)


def board_contents(
    cur: psycopg2.extras.RealDictCursor, board_id: int
) -> dict[str, object]:
    cur.execute(
        f"SELECT {CARD_FIELDS} FROM cards WHERE board_id = %s",
        (board_id,),
    )
    cards = [dict(c) for c in cur.fetchall()]
    cur.execute(
        """
        SELECT cn.id, cn.card_id_1, cn.card_id_2
        FROM connections cn
        JOIN cards c1 ON c1.id = cn.card_id_1
        JOIN cards c2 ON c2.id = cn.card_id_2
        WHERE c1.board_id = %s AND c2.board_id = %s
        """,
        (board_id, board_id),
    )
    connections = [dict(c) for c in cur.fetchall()]
    cur.execute(
        f"SELECT {NOTE_FIELDS} FROM notes WHERE board_id = %s",
        (board_id,),
    )
    notes = [dict(n) for n in cur.fetchall()]
    return {"cards": cards, "connections": connections, "notes": notes}


def get_board(
    cur: psycopg2.extras.RealDictCursor, board_id: int, user_id: int
) -> dict[str, object] | None:
    cur.execute(
        "SELECT id, name, share_token FROM boards WHERE id = %s AND user_id = %s",
        (board_id, user_id),
    )
    board = cur.fetchone()
    if board is None:
        return None
    return {"board": dict(board), **board_contents(cur, board_id)}


def rename_board(
    cur: psycopg2.extras.RealDictCursor, board_id: int, user_id: int, name: str
) -> dict[str, object] | None:
    cur.execute(
        "UPDATE boards SET name = %s WHERE id = %s AND user_id = %s RETURNING id, name",
        (name, board_id, user_id),
    )
    board = cur.fetchone()
    if board is None:
        return None
    return dict(board)


def delete_board(
    cur: psycopg2.extras.RealDictCursor, board_id: int, user_id: int
) -> None:
    cur.execute(
        "DELETE FROM boards WHERE id = %s AND user_id = %s",
        (board_id, user_id),
    )
