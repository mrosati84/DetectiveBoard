"""SQLAlchemy engine and per-request session lifecycle.

The engine and session factory are created lazily so that the ``DATABASE_*``
environment variables are read at first use rather than at import time. This
matters for the test suite, which sets ``DATABASE_NAME`` before importing
``app``, and for callers that load ``.env`` late.
"""

import os
from collections.abc import Generator, Mapping
from contextlib import contextmanager
from typing import cast
from urllib.parse import quote_plus

from sqlalchemy import Row, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def _url() -> str:
    """Build the PostgreSQL URL from ``DATABASE_*`` env vars.

    Mirrors ``migrations/env.py`` escaping via ``quote_plus`` so passwords with
    reserved characters behave identically. The explicit ``psycopg2`` driver is
    pinned to match the ``psycopg2-binary`` dependency that supplies the DBAPI.
    """
    return (
        f"postgresql+psycopg2://{quote_plus(os.getenv('DATABASE_USER', 'postgres'))}:"
        f"{quote_plus(os.getenv('DATABASE_PASSWORD', 'postgres'))}@"
        f"{os.getenv('DATABASE_HOST', 'localhost')}:"
        f"{os.getenv('DATABASE_PORT', '5432')}/"
        f"{os.getenv('DATABASE_NAME', 'postgres')}"
    )


def get_engine() -> Engine:
    """Return the process-wide engine, creating it on first use."""
    global _engine
    if _engine is None:
        _engine = create_engine(
            _url(),
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=5,
            pool_recycle=1800,
            pool_timeout=30,
        )
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """Return the process-wide session factory, creating it on first use."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=get_engine(),
            autoflush=False,
            expire_on_commit=False,
        )
    return _SessionLocal


@contextmanager
def db_session() -> Generator[Session, None, None]:
    """Yield a :class:`~sqlalchemy.orm.Session`.

    Mirrors the legacy raw-cursor context manager: callers keep explicit
    ``session.commit()`` / ``session.rollback()``. On exception the session is
    rolled back and the exception re-raised; the session is always closed.
    """
    session = get_session_factory()()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def row_to_dict[_RowT: tuple[object, ...]](row: Row[_RowT]) -> dict[str, object]:
    """Convert a SQLAlchemy ``Row`` to a plain ``dict``.

    ``dict(row)`` raises ``TypeError`` in SQLAlchemy 2.0; ``row._mapping`` is
    the supported conversion path and yields the same Python types as the
    legacy dict-cursor rows. ``_mapping`` is accessed via ``getattr``/``cast``
    only so the protected-member typing rule stays clean.
    """
    mapping = cast("Mapping[str, object]", getattr(row, "_mapping"))
    return dict(mapping)
