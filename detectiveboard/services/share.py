"""Board sharing: token lifecycle and public payload assembly."""

import secrets
from typing import cast

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from detectiveboard.database import row_to_dict
from detectiveboard.models import Board
from detectiveboard.services.boards import board_contents


def enable_share(session: Session, board_id: int) -> str:
    token = secrets.token_urlsafe(24)
    _ = session.execute(
        update(Board)
        .where(Board.id == board_id)
        .values(share_token=token)
        .returning(Board.share_token)
    )
    return token


def disable_share(session: Session, board_id: int) -> None:
    _ = session.execute(
        update(Board).where(Board.id == board_id).values(share_token=None)
    )


def get_board_id_by_share_token(session: Session, token: str) -> int | None:
    row = session.execute(select(Board.id).where(Board.share_token == token)).first()
    if row is None:
        return None
    return cast("int", row[0])


def get_shared_board_payload(session: Session, token: str) -> dict[str, object] | None:
    row = session.execute(
        select(Board.id, Board.name).where(Board.share_token == token)
    ).first()
    if row is None:
        return None
    board = row_to_dict(row)
    board_id = cast("int", board["id"])
    return {"board": board, **board_contents(session, board_id)}
