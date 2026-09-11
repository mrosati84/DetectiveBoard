"""Board API endpoints."""

from typing import cast

from flask import Blueprint, Response, jsonify

from detectiveboard.auth import current_user_id, json_body, require_auth
from detectiveboard.db import db_cursor
from detectiveboard.services import boards as boards_service

bp = Blueprint("boards", __name__)


@bp.route("/api/boards", methods=["GET"])
@require_auth
def list_boards() -> Response:
    with db_cursor() as cur:
        boards = boards_service.list_boards(cur, current_user_id())
    return jsonify(boards)


@bp.route("/api/boards", methods=["POST"])
@require_auth
def create_board() -> tuple[Response, int]:
    data = json_body()
    name = cast("str", data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Name is required"}), 400
    with db_cursor() as cur:
        board = boards_service.create_board(cur, current_user_id(), name)
        cur.connection.commit()
    return jsonify(board), 201


@bp.route("/api/boards/<int:board_id>", methods=["GET"])
@require_auth
def get_board(board_id: int) -> Response | tuple[Response, int]:
    with db_cursor() as cur:
        board = boards_service.get_board(cur, board_id, current_user_id())
    if board is None:
        return jsonify({"error": "Board not found"}), 404
    return jsonify(board)


@bp.route("/api/boards/<int:board_id>", methods=["PATCH"])
@require_auth
def rename_board(board_id: int) -> Response | tuple[Response, int]:
    data = json_body()
    name = cast("str", data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Name is required"}), 400
    with db_cursor() as cur:
        board = boards_service.rename_board(cur, board_id, current_user_id(), name)
        cur.connection.commit()
    if board is None:
        return jsonify({"error": "Board not found"}), 404
    return jsonify(board)


@bp.route("/api/boards/<int:board_id>", methods=["DELETE"])
@require_auth
def delete_board(board_id: int) -> Response:
    with db_cursor() as cur:
        boards_service.delete_board(cur, board_id, current_user_id())
        cur.connection.commit()
    return jsonify({"success": True})
