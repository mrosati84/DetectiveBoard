"""Shared pytest fixtures for the DetectiveBoard characterization suite.

The environment variables below MUST be set before ``app`` is imported so that
``load_dotenv(override=False)`` inside ``detectiveboard/__init__.py`` cannot
override them.
"""

import os

os.environ["DATABASE_NAME"] = "detectiveboard_test"
os.environ["RATE_LIMIT_STORAGE_URI"] = "memory://"
# Long enough to satisfy PyJWT's InsecureKeyLengthWarning; the dev .env key is
# only 10 bytes. Pinned before the app imports so load_dotenv cannot override it.
os.environ["SECRET_KEY"] = "detectiveboard-test-secret-key-0123456789abcdef"

import subprocess  # noqa: E402
from collections.abc import Iterator  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import cast  # noqa: E402

import psycopg2  # noqa: E402
import pytest  # noqa: E402
from flask.testing import FlaskClient  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ADMIN_DATABASE = "postgres"
TEST_DATABASE = "detectiveboard_test"


def _connect(dbname: str) -> psycopg2.extensions.connection:
    return psycopg2.connect(
        host=os.getenv("DATABASE_HOST", "localhost"),
        port=int(os.getenv("DATABASE_PORT", "5432")),
        user=os.getenv("DATABASE_USER", "postgres"),
        password=os.getenv("DATABASE_PASSWORD", "postgres"),
        dbname=dbname,
    )


def _ensure_test_database() -> None:
    conn = _connect(ADMIN_DATABASE)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname=%s", (TEST_DATABASE,))
            if cur.fetchone() is None:
                cur.execute(f'CREATE DATABASE "{TEST_DATABASE}"')
    finally:
        conn.close()


def _apply_migrations() -> None:
    _ = subprocess.run(
        ["uv", "run", "alembic", "upgrade", "head"],
        cwd=PROJECT_ROOT,
        env={**os.environ, "DATABASE_NAME": TEST_DATABASE},
        check=True,
    )


def _public_tables(conn: psycopg2.extensions.connection) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            AND table_name <> 'alembic_version'
            """
        )
        rows = cast("list[tuple[object, ...]]", cur.fetchall())
        return [str(row[0]) for row in rows]


_ensure_test_database()
_apply_migrations()

from app import app  # noqa: E402
from detectiveboard.extensions import limiter  # noqa: E402


@pytest.fixture
def client() -> FlaskClient:
    app.config["TESTING"] = True
    return app.test_client()


@pytest.fixture
def error_client() -> Iterator[FlaskClient]:
    """Client that renders unhandled exceptions as HTTP 500 responses.

    Used to characterize endpoints whose current implementation raises; with the
    regular ``client`` fixture, ``TESTING``/propagation would re-raise instead of
    returning a 500, so propagation is explicitly disabled here.
    """
    app.config["TESTING"] = True
    app.config["PROPAGATE_EXCEPTIONS"] = False
    try:
        yield app.test_client()
    finally:
        app.config["PROPAGATE_EXCEPTIONS"] = None


@pytest.fixture(autouse=True)
def _clean_state() -> Iterator[None]:
    conn = _connect(TEST_DATABASE)
    try:
        tables = _public_tables(conn)
        if tables:
            quoted = ", ".join(f'"{table}"' for table in tables)
            with conn.cursor() as cur:
                cur.execute(f"TRUNCATE {quoted} RESTART IDENTITY CASCADE")
        conn.commit()
    finally:
        conn.close()
    limiter.reset()
    yield


__all__ = ["_clean_state"]
