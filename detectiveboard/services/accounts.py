"""Account persistence for register/login/me."""

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from detectiveboard.database import row_to_dict
from detectiveboard.models import User


def create_user(session: Session, email: str, password_hash: str) -> dict[str, object]:
    row = session.execute(
        insert(User)
        .values(email=email, password_hash=password_hash)
        .returning(User.id, User.email)
    ).one()
    return row_to_dict(row)


def get_user_by_email(session: Session, email: str) -> dict[str, object] | None:
    row = session.execute(
        select(User.id, User.email, User.password_hash).where(User.email == email)
    ).first()
    if row is None:
        return None
    return row_to_dict(row)


def get_user_by_id(session: Session, user_id: int) -> dict[str, object] | None:
    row = session.execute(select(User.id, User.email).where(User.id == user_id)).first()
    if row is None:
        return None
    return row_to_dict(row)
