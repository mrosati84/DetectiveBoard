"""Board sharing API endpoints."""

from flask import Blueprint, Response, jsonify

from detectiveboard.auth import current_user_id, require_auth
from detectiveboard.db import db_cursor
from detectiveboard.services import boards as boards_service
from detectiveboard.services import share as share_service

bp = Blueprint("share", __name__)


@bp.route("/api/boards/<int:board_id>/share", methods=["POST"])
@require_auth
def enable_share(board_id: int) -> Response | tuple[Response, int]:
    with db_cursor() as cur:
        if not boards_service.board_is_owned(cur, board_id, current_user_id()):
            return jsonify({"error": "Board not found"}), 404
        token = share_service.enable_share(cur, board_id)
        cur.connection.commit()
    return jsonify({"share_token": token, "share_url": f"/share/{token}"})


@bp.route("/api/boards/<int:board_id>/share", methods=["DELETE"])
@require_auth
def disable_share(board_id: int) -> Response | tuple[Response, int]:
    with db_cursor() as cur:
        if not boards_service.board_is_owned(cur, board_id, current_user_id()):
            return jsonify({"error": "Board not found"}), 404
        share_service.disable_share(cur, board_id)
        cur.connection.commit()
    return jsonify({"ok": True})


@bp.route("/api/share/<token>", methods=["GET"])
def get_shared_board(token: str) -> Response | tuple[Response, int]:
    with db_cursor() as cur:
        payload = share_service.get_shared_board_payload(cur, token)
    if payload is None:
        return jsonify({"error": "Board not found"}), 404
    return jsonify(payload)
