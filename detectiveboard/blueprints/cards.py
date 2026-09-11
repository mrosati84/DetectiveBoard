"""Card API endpoints."""

from flask import Blueprint, Response, jsonify, request

from detectiveboard.auth import current_user_id, json_body, require_auth
from detectiveboard.config import ALLOWED_CARD_COLORS
from detectiveboard.database import db_session
from detectiveboard.services import boards as boards_service
from detectiveboard.services import cards as cards_service
from detectiveboard.services.uploads import save_uploaded_card_image

bp = Blueprint("cards", __name__)


@bp.route("/api/boards/<int:board_id>/cards", methods=["POST"])
@require_auth
def create_card(board_id: int) -> Response | tuple[Response, int]:
    with db_session() as session:
        if not boards_service.board_is_owned(session, board_id, current_user_id()):
            return jsonify({"error": "Board not found"}), 404

        title = (request.form.get("title") or "").strip()
        description = (request.form.get("description") or "").strip() or None
        pos_x = float(request.form.get("pos_x", 200))
        pos_y = float(request.form.get("pos_y", 150))
        pin_position = request.form.get("pin_position", "center")
        if pin_position not in ("left", "center", "right"):
            pin_position = "center"
        inactive = request.form.get("inactive") == "true"
        color = request.form.get("color") or None
        if color and color not in ALLOWED_CARD_COLORS:
            color = None

        if not title:
            return jsonify({"error": "Title is required"}), 400

        try:
            image_path = save_uploaded_card_image(request.files.get("image"))
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        card = cards_service.create_card(
            session,
            board_id,
            title,
            description,
            pos_x,
            pos_y,
            pin_position,
            inactive,
            color,
            image_path,
        )
        session.commit()
    return jsonify(card), 201


@bp.route("/api/cards/<int:card_id>", methods=["PUT"])
@require_auth
def update_card(card_id: int) -> Response | tuple[Response, int]:
    with db_session() as session:
        if not cards_service.card_is_owned(session, card_id, current_user_id()):
            return jsonify({"error": "Card not found"}), 404

        updates: dict[str, object] = {}
        content_type = request.content_type or ""
        if "multipart/form-data" in content_type:
            title = (request.form.get("title") or "").strip()
            description = (request.form.get("description") or "").strip() or None
            if not title:
                return jsonify({"error": "Title is required"}), 400
            updates["title"] = title
            updates["description"] = description
            pin_position = request.form.get("pin_position")
            if pin_position in ("left", "center", "right"):
                updates["pin_position"] = pin_position
            updates["inactive"] = request.form.get("inactive") == "true"
            color = request.form.get("color") or None
            if color and color not in ALLOWED_CARD_COLORS:
                color = None
            updates["color"] = color
            try:
                image_path = save_uploaded_card_image(request.files.get("image"))
            except ValueError as exc:
                return jsonify({"error": str(exc)}), 400
            if image_path:
                updates["image_path"] = image_path
        else:
            data = json_body()
            for field in ("pos_x", "pos_y", "title", "description", "color"):
                if field in data:
                    updates[field] = data[field]
            if not updates:
                return jsonify({"error": "Nothing to update"}), 400

        card = cards_service.update_card(session, card_id, updates)
        session.commit()
    return jsonify(card)


@bp.route("/api/cards/<int:card_id>", methods=["DELETE"])
@require_auth
def delete_card(card_id: int) -> Response | tuple[Response, int]:
    with db_session() as session:
        if not cards_service.card_is_owned(session, card_id, current_user_id()):
            return jsonify({"error": "Card not found"}), 404
        cards_service.delete_card(session, card_id)
        session.commit()
    return jsonify({"success": True})
