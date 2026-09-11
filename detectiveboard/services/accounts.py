"""Account persistence for register/login/me."""

import psycopg2.extras


def create_user(
    cur: psycopg2.extras.RealDictCursor, email: str, password_hash: str
) -> dict[str, object]:
    cur.execute(
        "INSERT INTO users (email, password_hash) VALUES (%s, %s) RETURNING id, email",
        (email, password_hash),
    )
    row = cur.fetchone()
    assert row is not None
    return dict(row)


def get_user_by_email(
    cur: psycopg2.extras.RealDictCursor, email: str
) -> dict[str, object] | None:
    cur.execute("SELECT id, email, password_hash FROM users WHERE email = %s", (email,))
    row = cur.fetchone()
    if row is None:
        return None
    return dict(row)


def get_user_by_id(
    cur: psycopg2.extras.RealDictCursor, user_id: int
) -> dict[str, object] | None:
    cur.execute("SELECT id, email FROM users WHERE id = %s", (user_id,))
    row = cur.fetchone()
    if row is None:
        return None
    return dict(row)
