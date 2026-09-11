"""Note API endpoints."""

from typing import cast

from flask import Blueprint, Response, jsonify

from detectiveboard.auth import current_user_id, json_body, require_auth
from detectiveboard.db import db_cursor
from detectiveboard.services import boards as boards_service
from detectiveboard.services import notes as notes_service

bp = Blueprint("notes", __name__)


@bp.route("/api/boards/<int:board_id>/notes", methods=["POST"])
@require_auth
def create_note(board_id: int) -> Response | tuple[Response, int]:
    with db_cursor() as cur:
        if not boards_service.board_is_owned(cur, board_id, current_user_id()):
            return jsonify({"error": "Board not found"}), 404

        data = json_body()
        content = cast("str", data.get("content") or "").strip()
        pos_x = float(cast("int", data.get("pos_x", 200)))
        pos_y = float(cast("int", data.get("pos_y", 150)))
        note = notes_service.create_note(cur, board_id, content, pos_x, pos_y)
        cur.connection.commit()
    return jsonify(note), 201


@bp.route("/api/notes/<int:note_id>", methods=["PUT"])
@require_auth
def update_note(note_id: int) -> Response | tuple[Response, int]:
    with db_cursor() as cur:
        if not notes_service.note_is_owned(cur, note_id, current_user_id()):
            return jsonify({"error": "Note not found"}), 404

        data = json_body()
        updates: dict[str, object] = {}
        for field in ("content", "pos_x", "pos_y"):
            if field in data:
                updates[field] = data[field]
        if not updates:
            return jsonify({"error": "Niente da aggiornare"}), 400
        note = notes_service.update_note(cur, note_id, updates)
        cur.connection.commit()
    return jsonify(note)


@bp.route("/api/notes/<int:note_id>", methods=["DELETE"])
@require_auth
def delete_note(note_id: int) -> Response | tuple[Response, int]:
    with db_cursor() as cur:
        if not notes_service.note_is_owned(cur, note_id, current_user_id()):
            return jsonify({"error": "Note not found"}), 404
        notes_service.delete_note(cur, note_id)
        cur.connection.commit()
    return jsonify({"success": True})
