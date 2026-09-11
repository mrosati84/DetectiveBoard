"""App-level HTTP error handlers."""

from flask import Flask, Response, jsonify, render_template, request
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge

from detectiveboard.config import UPLOAD_TOO_LARGE_MESSAGE


def ratelimit_handler(_e: HTTPException) -> tuple[Response, int]:
    return jsonify({"error": "Too many requests. Try again later."}), 429


def request_entity_too_large(
    _e: RequestEntityTooLarge,
) -> tuple[Response, int] | tuple[str, int]:
    if request.path.startswith("/api/"):
        return jsonify({"error": UPLOAD_TOO_LARGE_MESSAGE}), 413
    return UPLOAD_TOO_LARGE_MESSAGE, 413


def page_not_found(_e: HTTPException) -> tuple[str, int]:
    return render_template("404.html"), 404


def register_error_handlers(app: Flask) -> None:
    app.register_error_handler(429, ratelimit_handler)
    app.register_error_handler(RequestEntityTooLarge, request_entity_too_large)
    app.register_error_handler(404, page_not_found)
