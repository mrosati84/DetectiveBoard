"""Note API endpoints."""

from typing import cast

from flask import Blueprint, Response, jsonify

from detectiveboard.auth import current_user_id, json_body, require_auth
from detectiveboard.database import db_session
from detectiveboard.services import boards as boards_service
from detectiveboard.services import notes as notes_service

bp = Blueprint("notes", __name__)


@bp.route("/api/boards/<int:board_id>/notes", methods=["POST"])
@require_auth
def create_note(board_id: int) -> Response | tuple[Response, int]:
    with db_session() as session:
        if not boards_service.board_is_owned(session, board_id, current_user_id()):
            return jsonify({"error": "Board not found"}), 404

        data = json_body()
        content = cast("str", data.get("content") or "").strip()
        pos_x = float(cast("int", data.get("pos_x", 200)))
        pos_y = float(cast("int", data.get("pos_y", 150)))
        note = notes_service.create_note(session, board_id, content, pos_x, pos_y)
        session.commit()
    return jsonify(note), 201


@bp.route("/api/notes/<int:note_id>", methods=["PUT"])
@require_auth
def update_note(note_id: int) -> Response | tuple[Response, int]:
    with db_session() as session:
        if not notes_service.note_is_owned(session, note_id, current_user_id()):
            return jsonify({"error": "Note not found"}), 404

        data = json_body()
        updates: dict[str, object] = {}
        for field in ("content", "pos_x", "pos_y"):
            if field in data:
                updates[field] = data[field]
        if not updates:
            return jsonify({"error": "Niente da aggiornare"}), 400
        note = notes_service.update_note(session, note_id, updates)
        session.commit()
    return jsonify(note)


@bp.route("/api/notes/<int:note_id>", methods=["DELETE"])
@require_auth
def delete_note(note_id: int) -> Response | tuple[Response, int]:
    with db_session() as session:
        if not notes_service.note_is_owned(session, note_id, current_user_id()):
            return jsonify({"error": "Note not found"}), 404
        notes_service.delete_note(session, note_id)
        session.commit()
    return jsonify({"success": True})
