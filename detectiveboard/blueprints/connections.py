"""Connection (red yarn) API endpoints."""

from typing import cast

from flask import Blueprint, Response, jsonify
from sqlalchemy.exc import IntegrityError

from detectiveboard.auth import current_user_id, json_body, require_auth
from detectiveboard.database import db_session
from detectiveboard.services import connections as connections_service

bp = Blueprint("connections", __name__)


@bp.route("/api/connections", methods=["POST"])
@require_auth
def create_connection() -> Response | tuple[Response, int]:
    data = json_body()
    id1 = cast("int", data.get("card_id_1"))
    id2 = cast("int", data.get("card_id_2"))
    if not id1 or not id2:
        return jsonify({"error": "Both card IDs are required"}), 400
    if id1 > id2:
        id1, id2 = id2, id1

    with db_session() as session:
        if not connections_service.both_cards_owned(
            session, current_user_id(), id1, id2
        ):
            return jsonify({"error": "Card not found"}), 404

        try:
            connection = connections_service.create_connection(session, id1, id2)
            session.commit()
        except IntegrityError:
            session.rollback()
            return jsonify({"error": "Connection already exists"}), 409
    return jsonify(connection), 201


@bp.route("/api/connections", methods=["DELETE"])
@require_auth
def delete_connection() -> Response | tuple[Response, int]:
    data = json_body()
    id1 = cast("int", data.get("card_id_1"))
    id2 = cast("int", data.get("card_id_2"))
    if id1 > id2:
        id1, id2 = id2, id1

    with db_session() as session:
        if not connections_service.both_cards_owned(
            session, current_user_id(), id1, id2
        ):
            return jsonify({"error": "Card not found"}), 404

        connections_service.delete_connection(session, id1, id2)
        session.commit()
    return jsonify({"success": True})
