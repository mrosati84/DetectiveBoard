"""Application configuration constants and environment-driven settings."""

import os
from pathlib import Path

from flask import Flask

BASE_DIR = Path(__file__).resolve().parent.parent

MAX_IMAGE_BYTES = 1 * 1024 * 1024
MAX_MULTIPART_OVERHEAD_BYTES = 64 * 1024
UPLOAD_TOO_LARGE_MESSAGE = "File too large. Maximum image size is 1 MB."
TOKEN_EXPIRY_DAYS = 30
ALLOWED_CARD_COLORS: set[str] = {"#f5e6c8", "#f5d0c8", "#d5e8d0", "#2a1e14"}


def load_config(app: Flask) -> None:
    """Populate ``app.config`` from the environment.

    All environment reads happen here at call time, never at module import.
    """
    secret_key = os.getenv("SECRET_KEY")
    if not secret_key:
        raise RuntimeError("SECRET_KEY environment variable must be set")
    app.config["SECRET_KEY"] = secret_key
    app.config["MAX_CONTENT_LENGTH"] = MAX_IMAGE_BYTES + MAX_MULTIPART_OVERHEAD_BYTES
    app.config["RATE_LIMIT_AUTH"] = os.getenv("RATE_LIMIT_AUTH", "5 per minute")
    app.config["RATELIMIT_STORAGE_URI"] = os.getenv(
        "RATE_LIMIT_STORAGE_URI", "memory://"
    )
    app.config["UPLOAD_FOLDER"] = os.environ.get("UPLOAD_FOLDER") or os.path.join(
        str(app.static_folder), "uploads"
    )
