"""Card image upload handling."""

import os
import uuid
from typing import cast

from flask import current_app
from werkzeug.datastructures import FileStorage

from detectiveboard.config import MAX_IMAGE_BYTES, UPLOAD_TOO_LARGE_MESSAGE


def save_uploaded_card_image(file: FileStorage | None) -> str | None:
    if not file or not file.filename:
        return None

    parts = file.filename.rsplit(".", 1)
    if len(parts) != 2:
        raise ValueError("Only jpg/png images are accepted")

    ext = parts[-1].lower()
    if ext not in ("jpg", "jpeg", "png"):
        raise ValueError("Only jpg/png images are accepted")

    _ = file.stream.seek(0, os.SEEK_END)
    file_size = file.stream.tell()
    _ = file.stream.seek(0)
    if file_size > MAX_IMAGE_BYTES:
        raise ValueError(UPLOAD_TOO_LARGE_MESSAGE)

    filename = f"{uuid.uuid4().hex}.{ext}"
    upload_folder = cast("str", current_app.config["UPLOAD_FOLDER"])
    file.save(os.path.join(upload_folder, filename))
    return f"/static/uploads/{filename}"
