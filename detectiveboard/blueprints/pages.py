"""HTML pages and static asset serving."""

from flask import Blueprint, Response, jsonify, render_template, send_from_directory

from detectiveboard.config import BASE_DIR
from detectiveboard.db import db_cursor
from detectiveboard.services import share as share_service

bp = Blueprint("pages", __name__)


@bp.route("/health")
def health() -> Response:
    return jsonify({"message": "OK"})


@bp.route("/assets/<path:filename>")
def serve_assets(filename: str) -> Response:
    return send_from_directory(str(BASE_DIR / "assets"), filename)


@bp.route("/")
def home() -> str:
    return render_template("home.html")


@bp.route("/board")
def board() -> str:
    return render_template("index.html")


@bp.route("/share/<token>")
def share_board(token: str) -> str | tuple[str, int]:
    with db_cursor() as cur:
        board_id = share_service.get_board_id_by_share_token(cur, token)
    if board_id is None:
        return (
            render_template(
                "404.html",
                page_title="Board not found",
                page_message="This board is no longer shared or the link is invalid.",
            ),
            404,
        )
    return render_template("shared.html", token=token)
