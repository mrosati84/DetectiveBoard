"""Board sharing: token lifecycle and public payload assembly."""

import secrets
from typing import cast

import psycopg2.extras

from detectiveboard.services.boards import board_contents


def enable_share(cur: psycopg2.extras.RealDictCursor, board_id: int) -> str:
    token = secrets.token_urlsafe(24)
    cur.execute(
        "UPDATE boards SET share_token = %s WHERE id = %s RETURNING share_token",
        (token, board_id),
    )
    return token


def disable_share(cur: psycopg2.extras.RealDictCursor, board_id: int) -> None:
    cur.execute("UPDATE boards SET share_token = NULL WHERE id = %s", (board_id,))


def get_board_id_by_share_token(
    cur: psycopg2.extras.RealDictCursor, token: str
) -> int | None:
    cur.execute("SELECT id FROM boards WHERE share_token = %s", (token,))
    row = cur.fetchone()
    if row is None:
        return None
    return cast("int", row["id"])


def get_shared_board_payload(
    cur: psycopg2.extras.RealDictCursor, token: str
) -> dict[str, object] | None:
    cur.execute("SELECT id, name FROM boards WHERE share_token = %s", (token,))
    board = cur.fetchone()
    if board is None:
        return None
    board_dict = dict(board)
    board_id = cast("int", board_dict["id"])
    return {"board": board_dict, **board_contents(cur, board_id)}
