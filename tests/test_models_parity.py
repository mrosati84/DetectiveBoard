"""Parity tests for the SQLAlchemy models against the live test database.

These tests are the Phase 1 safety net: they prove ``detectiveboard.models``
matches the migrated schema exactly (without touching any call site), that no
ORM relationships/cascades were introduced, and that ``row_to_dict`` is the
correct serialization path for SQLAlchemy ``Row`` objects.
"""

from __future__ import annotations

from typing import cast

import pytest
from sqlalchemy import (
    REAL,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
    insert,
    inspect,
    literal,
    select,
    update,
)
from sqlalchemy.engine import Inspector
from sqlalchemy.orm import Mapper
from sqlalchemy.schema import DefaultClause
from sqlalchemy.sql.type_api import TypeEngine

from detectiveboard.database import db_session, get_engine, row_to_dict
from detectiveboard.models import Base, Board, Card, Connection, Note, User

MAPPED_TABLES = ("boards", "cards", "connections", "notes", "users")
MAPPED_MODELS: tuple[type[Base], ...] = (User, Board, Card, Connection, Note)

CARD_COLUMNS = (
    "id",
    "board_id",
    "title",
    "description",
    "image_path",
    "pos_x",
    "pos_y",
    "pin_position",
    "inactive",
    "color",
)


def _inspector() -> Inspector:
    return inspect(get_engine())


def _type_family[T](type_: TypeEngine[T]) -> str:
    """Return a canonical type-family key for a SQLAlchemy type.

    The mapping is deliberately granular enough to catch drift the old
    ``python_type`` check collapsed:

    * PostgreSQL ``REAL`` is distinguished from ``DOUBLE PRECISION``. Plain
      generic ``Float`` maps to the double-precision family because
      PostgreSQL's ``FLOAT`` without precision is an alias for
      ``double precision``.
    * ``TIMESTAMP`` (``timezone=False``) is distinguished from ``TIMESTAMPTZ``
      (``timezone=True``), both of which subclass ``DateTime``.
    * ``TEXT``/``VARCHAR`` and ``BIGINT``/``INTEGER`` remain distinct families.
    """
    if isinstance(type_, REAL):
        return "real"
    if isinstance(type_, Float):
        return "double_precision"
    if isinstance(type_, Boolean):
        return "boolean"
    if isinstance(type_, DateTime):
        return "timestamptz" if type_.timezone else "timestamp"
    if isinstance(type_, BigInteger):
        return "bigint"
    if isinstance(type_, Integer):
        return "integer"
    if isinstance(type_, Text):
        return "text"
    if isinstance(type_, String):
        return "varchar"
    return type(type_).__name__.lower()


def test_type_family_distinguishes_precision_and_timezone() -> None:
    real = cast("TypeEngine[object]", REAL())
    assert _type_family(Float()) == "double_precision"
    assert _type_family(real) == "real"
    assert _type_family(Float()) != _type_family(real)
    assert _type_family(DateTime(timezone=False)) == "timestamp"
    assert _type_family(DateTime(timezone=True)) == "timestamptz"


def _normalize_default(value: str | None) -> str | None:
    """Strip surrounding whitespace and a trailing PostgreSQL cast."""
    if value is None:
        return None
    return value.strip().split("::", 1)[0].strip()


def _model_default(column: Column[object]) -> str | None:
    default = column.server_default
    if not isinstance(default, DefaultClause):
        return None
    arg = getattr(default, "arg", None)
    if arg is None:
        return None
    return str(cast("object", arg))


@pytest.mark.parametrize("table_name", MAPPED_TABLES)
def test_columns_match_live_schema(table_name: str) -> None:
    reflected = {col["name"]: col for col in _inspector().get_columns(table_name)}
    table = Base.metadata.tables[table_name]

    assert set(reflected) == set(table.columns.keys()), table_name
    for column in table.columns:
        live = reflected[column.name]
        assert live["nullable"] == column.nullable, column.name
        assert _type_family(live["type"]) == _type_family(column.type), column.name


@pytest.mark.parametrize("table_name", MAPPED_TABLES)
def test_server_defaults_match_live_schema(table_name: str) -> None:
    reflected = {col["name"]: col for col in _inspector().get_columns(table_name)}
    table = Base.metadata.tables[table_name]

    for column in table.columns:
        if column.primary_key:
            # The PK default is a DB-owned SERIAL sequence, not a model default.
            continue
        live = reflected[column.name]["default"]
        declared = _model_default(column)
        assert _normalize_default(live) == _normalize_default(declared), column.name


@pytest.mark.parametrize("table_name", MAPPED_TABLES)
def test_foreign_keys_match_and_cascade(table_name: str) -> None:
    table = Base.metadata.tables[table_name]
    declared = {
        fk.parent.name: (fk.column.table.name, fk.column.name, fk.ondelete)
        for fk in table.foreign_keys
    }
    live: dict[str, tuple[str, str, str | None]] = {}
    for fk in _inspector().get_foreign_keys(table_name):
        options: dict[str, object] = fk.get("options") or {}
        live[fk["constrained_columns"][0]] = (
            fk["referred_table"],
            fk["referred_columns"][0],
            cast("str | None", options.get("ondelete")),
        )
    assert declared == live, table_name
    for _, _, ondelete in live.values():
        assert ondelete == "CASCADE", table_name


@pytest.mark.parametrize("table_name", MAPPED_TABLES)
def test_unique_constraints_match_live_schema(table_name: str) -> None:
    table = Base.metadata.tables[table_name]
    declared = {
        tuple(sorted(column.name for column in constraint.columns))
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    live = {
        tuple(sorted(constraint["column_names"]))
        for constraint in _inspector().get_unique_constraints(table_name)
    }
    assert declared == live, table_name


@pytest.mark.parametrize("model", MAPPED_MODELS)
def test_no_orm_relationships_or_cascades(model: type[Base]) -> None:
    mapper: Mapper[object] = model.__mapper__
    assert len(list(mapper.relationships)) == 0


def test_core_crud_round_trip() -> None:
    with db_session() as session:
        user_row = session.execute(
            insert(User)
            .values(email="parity@example.com", password_hash="hash")
            .returning(User.id, User.email)
        ).one()
        user = row_to_dict(user_row)
        assert set(user) == {"id", "email"}
        assert user["email"] == "parity@example.com"
        user_id = cast(int, user["id"])

        board_row = session.execute(
            insert(Board)
            .values(name="Parity", user_id=user_id)
            .returning(
                Board.id, Board.name, Board.created_at, Board.user_id, Board.share_token
            )
        ).one()
        board = row_to_dict(board_row)
        assert set(board) == {"id", "name", "created_at", "user_id", "share_token"}
        assert board["name"] == "Parity"
        board_id = cast(int, board["id"])

        card_row = session.execute(
            insert(Card)
            .values(board_id=board_id, title="Card")
            .returning(*Card.__table__.columns)
        ).one()
        card = row_to_dict(card_row)
        assert set(card) == set(CARD_COLUMNS)
        assert card["title"] == "Card"
        assert card["pin_position"] == "center"
        assert card["inactive"] is False
        assert card["pos_x"] == 100.0
        assert card["pos_y"] == 100.0
        card_id = cast(int, card["id"])

        updated_row = session.execute(
            update(Card)
            .where(Card.id == card_id)
            .values(title="Card updated")
            .returning(Card.id, Card.title)
        ).one()
        assert row_to_dict(updated_row) == {"id": card_id, "title": "Card updated"}

        selected_row = session.execute(
            select(Card.id, Card.title, Card.pos_x).where(Card.id == card_id)
        ).one()
        assert row_to_dict(selected_row) == {
            "id": card_id,
            "title": "Card updated",
            "pos_x": 100.0,
        }

        # No commit: closing the session rolls back the transaction.
        session.rollback()


def test_dict_of_row_requires_mapping() -> None:
    """``dict(row)`` raises; ``dict(row._mapping)`` works (regression guard)."""
    with db_session() as session:
        row = session.execute(
            select(literal(1).label("n"), literal("x").label("s"))
        ).one()

    with pytest.raises(TypeError):
        _ = dict(row)

    assert row_to_dict(row) == {"n": 1, "s": "x"}
