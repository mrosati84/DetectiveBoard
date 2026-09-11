"""SQLAlchemy declarative models mirroring the live DetectiveBoard schema.

These models are the single canonical definition of the five application
tables. ``todos`` is deliberately not mapped (it is an untracked table with no
application code using it). No ORM ``relationship()`` is defined: cascades are
DB-level (``ON DELETE CASCADE``) and must stay there so delete semantics are
unchanged.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base for all mapped tables."""


class User(Base):
    __tablename__: str = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False),
        nullable=True,
        server_default=text("CURRENT_TIMESTAMP"),
    )


class Board(Base):
    __tablename__: str = "boards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False),
        nullable=True,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    share_token: Mapped[str | None] = mapped_column(Text, unique=True, nullable=True)


class Card(Base):
    __tablename__: str = "cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    board_id: Mapped[int | None] = mapped_column(
        ForeignKey("boards.id", ondelete="CASCADE"), nullable=True
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    pos_x: Mapped[float] = mapped_column(
        Float, nullable=False, server_default=text("100")
    )
    pos_y: Mapped[float] = mapped_column(
        Float, nullable=False, server_default=text("100")
    )
    pin_position: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'center'")
    )
    inactive: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    color: Mapped[str | None] = mapped_column(Text, nullable=True)


class Connection(Base):
    __tablename__: str = "connections"
    __table_args__: tuple[UniqueConstraint, ...] = (
        UniqueConstraint("card_id_1", "card_id_2"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    card_id_1: Mapped[int | None] = mapped_column(
        ForeignKey("cards.id", ondelete="CASCADE"), nullable=True
    )
    card_id_2: Mapped[int | None] = mapped_column(
        ForeignKey("cards.id", ondelete="CASCADE"), nullable=True
    )


class Note(Base):
    __tablename__: str = "notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    board_id: Mapped[int | None] = mapped_column(
        ForeignKey("boards.id", ondelete="CASCADE"), nullable=True
    )
    content: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("''")
    )
    pos_x: Mapped[float] = mapped_column(
        Float, nullable=False, server_default=text("100")
    )
    pos_y: Mapped[float] = mapped_column(
        Float, nullable=False, server_default=text("100")
    )
