"""Authentication API endpoints."""

from typing import cast

from flask import Blueprint, Response, current_app, jsonify
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from detectiveboard.auth import (
    create_token,
    current_user_id,
    json_body,
    require_auth,
)
from detectiveboard.database import db_session
from detectiveboard.extensions import limiter
from detectiveboard.services import accounts

bp = Blueprint("auth", __name__)


@bp.route("/api/auth/register", methods=["POST"])
@limiter.limit(lambda: cast("str", current_app.config["RATE_LIMIT_AUTH"]))
def register() -> tuple[Response, int]:
    data = json_body()
    username = cast("str", data.get("username") or "").strip().lower()
    password = cast("str", data.get("password") or "")
    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400
    if "@" in username:
        return jsonify({"error": "Username cannot contain @"}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400

    password_hash = generate_password_hash(password)
    with db_session() as session:
        try:
            user = accounts.create_user(session, username, password_hash)
            session.commit()
        except IntegrityError:
            session.rollback()
            return jsonify({"error": "Username already taken"}), 409

    token = create_token(cast("int", user["id"]))
    return jsonify({"token": token, "username": cast("str", user["email"])}), 201


@bp.route("/api/auth/login", methods=["POST"])
@limiter.limit(lambda: cast("str", current_app.config["RATE_LIMIT_AUTH"]))
def login() -> Response | tuple[Response, int]:
    data = json_body()
    username = cast("str", data.get("username") or "").strip().lower()
    password = cast("str", data.get("password") or "")
    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    with db_session() as session:
        user = accounts.get_user_by_email(session, username)

    if not user or not check_password_hash(
        cast("str", user["password_hash"]), password
    ):
        return jsonify({"error": "Invalid username or password"}), 401

    token = create_token(cast("int", user["id"]))
    return jsonify({"token": token, "username": cast("str", user["email"])})


@bp.route("/api/auth/me", methods=["GET"])
@require_auth
def get_me() -> Response | tuple[Response, int]:
    with db_session() as session:
        user = accounts.get_user_by_id(session, current_user_id())
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify(
        {"id": cast("int", user["id"]), "username": cast("str", user["email"])}
    )
