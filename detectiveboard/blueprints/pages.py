"""HTML pages and static asset serving."""

from typing import cast

from flask import (
    Blueprint,
    Response,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
)
from werkzeug.wrappers.response import Response as WerkzeugResponse

from detectiveboard.config import BASE_DIR
from detectiveboard.database import db_session
from detectiveboard.services import share as share_service

bp = Blueprint("pages", __name__)

STATIC_IMG_DIR = BASE_DIR / "static" / "img"


def _site_url() -> str:
    return cast("str", current_app.config["SITE_URL"])


@bp.before_app_request
def redirect_www_to_apex() -> WerkzeugResponse | None:
    """Permanently redirect ``www.`` requests to the bare domain.

    Serving the same content on two hosts splits search ranking signals, so
    every ``www.`` URL is collapsed onto the canonical apex host.
    """
    host = request.host
    if not host.startswith("www."):
        return None
    target = f"https://{host[4:]}{request.full_path.rstrip('?')}"
    # 308 preserves method and body for non-GET API calls.
    code = 301 if request.method in ("GET", "HEAD") else 308
    return redirect(target, code=code)


@bp.app_context_processor
def inject_site_url() -> dict[str, str]:
    return {"site_url": _site_url()}


@bp.route("/health")
def health() -> Response:
    return jsonify({"message": "OK"})


@bp.route("/assets/<path:filename>")
def serve_assets(filename: str) -> Response:
    return send_from_directory(str(BASE_DIR / "assets"), filename)


@bp.route("/favicon.ico")
def favicon() -> Response:
    return send_from_directory(
        str(STATIC_IMG_DIR), "favicon.ico", mimetype="image/x-icon", max_age=86400
    )


@bp.route("/apple-touch-icon.png")
def apple_touch_icon() -> Response:
    return send_from_directory(str(STATIC_IMG_DIR), "apple-touch-icon.png", max_age=86400)


@bp.route("/robots.txt")
def robots_txt() -> Response:
    body = render_template("seo/robots.txt")
    return Response(body, mimetype="text/plain")


@bp.route("/sitemap.xml")
def sitemap_xml() -> Response:
    body = render_template("seo/sitemap.xml")
    return Response(body, mimetype="application/xml")


@bp.route("/site.webmanifest")
def web_manifest() -> Response:
    body = render_template("seo/site.webmanifest")
    return Response(body, mimetype="application/manifest+json")


@bp.route("/")
def home() -> str:
    return render_template("home.html")


@bp.route("/board")
def board() -> str:
    return render_template("index.html")


@bp.route("/share/<token>")
def share_board(token: str) -> str | tuple[str, int]:
    with db_session() as session:
        board_id = share_service.get_board_id_by_share_token(session, token)
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
