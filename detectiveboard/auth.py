"""Authentication helpers: token creation, request guards and JSON parsing."""

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import TypeVar, cast

import jwt as pyjwt
from flask import current_app, g, jsonify, request

from detectiveboard.config import TOKEN_EXPIRY_DAYS

_F = TypeVar("_F", bound=Callable[..., object])


def json_body() -> dict[str, object]:
    return cast("dict[str, object]", request.get_json())


def create_token(user_id: int) -> str:
    payload: dict[str, object] = {
        "user_id": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=TOKEN_EXPIRY_DAYS),
    }
    return pyjwt.encode(
        payload, cast("str", current_app.config["SECRET_KEY"]), algorithm="HS256"
    )


def current_user_id() -> int:
    return cast("int", g.user_id)


def require_auth(f: _F) -> _F:
    @wraps(f)
    def decorated(*args: object, **kwargs: object) -> object:
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Authentication required"}), 401
        token = auth_header[7:]
        try:
            payload = cast(
                "dict[str, object]",
                pyjwt.decode(
                    token,
                    cast("str", current_app.config["SECRET_KEY"]),
                    algorithms=["HS256"],
                ),
            )
            g.user_id = cast("int", payload["user_id"])
        except pyjwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except pyjwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401
        return f(*args, **kwargs)

    return cast("_F", decorated)
