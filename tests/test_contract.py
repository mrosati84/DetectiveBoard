"""Characterization tests pinning the HTTP contract of the unmodified app.py.

These tests intentionally assert exact status codes, error strings and response
shapes. They are the safety net for the upcoming package refactor: if a
migration changes observable behaviour, these tests fail loudly.
"""

import io
import uuid
from datetime import datetime, timedelta, timezone
from typing import cast

import jwt as pyjwt
from flask.testing import FlaskClient
from werkzeug.test import TestResponse

from app import app

SECRET_KEY: str = cast("str", app.config["SECRET_KEY"])

PASSWORD = "password123"
MAX_IMAGE_BYTES = 1 * 1024 * 1024
MAX_MULTIPART_OVERHEAD_BYTES = 64 * 1024
UPLOAD_TOO_LARGE_MESSAGE = "File too large. Maximum image size is 1 MB."


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _unique_username(prefix: str = "user") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _json(resp: TestResponse) -> dict[str, object]:
    body = cast("dict[str, object] | None", resp.get_json())
    assert body is not None, "expected a JSON response body"
    return body


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _assert_internal_server_error(resp: TestResponse) -> None:
    assert resp.status_code == 500
    assert resp.mimetype == "text/html"
    assert "Internal Server Error" in resp.get_data(as_text=True)


def _register(
    client: FlaskClient,
    username: str | None = None,
    password: str = PASSWORD,
) -> tuple[str, str]:
    if username is None:
        username = _unique_username()
    resp = client.post(
        "/api/auth/register", json={"username": username, "password": password}
    )
    assert resp.status_code == 201, resp.get_data(as_text=True)
    body = _json(resp)
    return cast("str", body["token"]), cast("str", body["username"])


def _create_board(client: FlaskClient, token: str, name: str = "Board") -> int:
    resp = client.post("/api/boards", json={"name": name}, headers=_auth(token))
    assert resp.status_code == 201, resp.get_data(as_text=True)
    return cast("int", _json(resp)["id"])


def _create_card(
    client: FlaskClient, token: str, board_id: int, title: str = "Card"
) -> int:
    resp = client.post(
        f"/api/boards/{board_id}/cards",
        data={"title": title},
        content_type="multipart/form-data",
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.get_data(as_text=True)
    return cast("int", _json(resp)["id"])


def _create_note(
    client: FlaskClient, token: str, board_id: int, content: str = "note"
) -> int:
    resp = client.post(
        f"/api/boards/{board_id}/notes",
        json={"content": content},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.get_data(as_text=True)
    return cast("int", _json(resp)["id"])


# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #


def test_register_missing_fields(client: FlaskClient) -> None:
    resp = client.post("/api/auth/register", json={})
    assert resp.status_code == 400
    assert _json(resp) == {"error": "Username and password are required"}


def test_register_username_with_at(client: FlaskClient) -> None:
    resp = client.post(
        "/api/auth/register", json={"username": "a@b", "password": PASSWORD}
    )
    assert resp.status_code == 400
    assert _json(resp) == {"error": "Username cannot contain @"}


def test_register_short_password(client: FlaskClient) -> None:
    resp = client.post(
        "/api/auth/register",
        json={"username": _unique_username(), "password": "1234567"},
    )
    assert resp.status_code == 400
    assert _json(resp) == {"error": "Password must be at least 8 characters"}


def test_register_success_lowercases_username(client: FlaskClient) -> None:
    username = "MixedCase_" + uuid.uuid4().hex[:8]
    resp = client.post(
        "/api/auth/register", json={"username": username, "password": PASSWORD}
    )
    assert resp.status_code == 201
    body = _json(resp)
    assert set(body) == {"token", "username"}
    assert body["username"] == username.lower()
    assert isinstance(body["token"], str) and body["token"]


def test_register_duplicate_username(client: FlaskClient) -> None:
    username = _unique_username()
    first = client.post(
        "/api/auth/register", json={"username": username, "password": PASSWORD}
    )
    assert first.status_code == 201
    second = client.post(
        "/api/auth/register", json={"username": username, "password": PASSWORD}
    )
    assert second.status_code == 409
    assert _json(second) == {"error": "Username already taken"}


def test_login_missing_fields(client: FlaskClient) -> None:
    resp = client.post("/api/auth/login", json={})
    assert resp.status_code == 400
    assert _json(resp) == {"error": "Username and password are required"}


def test_login_bad_credentials(client: FlaskClient) -> None:
    token, username = _register(client)
    assert token
    resp = client.post(
        "/api/auth/login", json={"username": username, "password": "wrongpassword"}
    )
    assert resp.status_code == 401
    assert _json(resp) == {"error": "Invalid username or password"}


def test_login_success(client: FlaskClient) -> None:
    _, username = _register(client)
    resp = client.post(
        "/api/auth/login", json={"username": username.upper(), "password": PASSWORD}
    )
    assert resp.status_code == 200
    body = _json(resp)
    assert set(body) == {"token", "username"}
    assert body["username"] == username


def test_me_requires_authentication(client: FlaskClient) -> None:
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401
    assert _json(resp) == {"error": "Authentication required"}


def test_me_rejects_invalid_token(client: FlaskClient) -> None:
    resp = client.get("/api/auth/me", headers=_auth("not-a-valid-token"))
    assert resp.status_code == 401
    assert _json(resp) == {"error": "Invalid token"}


def test_me_returns_current_user(client: FlaskClient) -> None:
    token, username = _register(client)
    resp = client.get("/api/auth/me", headers=_auth(token))
    assert resp.status_code == 200
    body = _json(resp)
    assert set(body) == {"id", "username"}
    assert body["username"] == username
    assert isinstance(body["id"], int)


def test_register_rate_limit(client: FlaskClient) -> None:
    statuses: list[int] = []
    last: TestResponse | None = None
    for _ in range(6):
        last = client.post(
            "/api/auth/register",
            json={"username": _unique_username(), "password": PASSWORD},
        )
        statuses.append(last.status_code)
    assert statuses[:5] == [201, 201, 201, 201, 201]
    assert last is not None
    assert last.status_code == 429
    assert _json(last) == {"error": "Too many requests. Try again later."}


# --------------------------------------------------------------------------- #
# Boards
# --------------------------------------------------------------------------- #


def test_list_boards_requires_auth(client: FlaskClient) -> None:
    resp = client.get("/api/boards")
    assert resp.status_code == 401
    assert _json(resp) == {"error": "Authentication required"}


def test_list_boards_empty(client: FlaskClient) -> None:
    token, _ = _register(client)
    resp = client.get("/api/boards", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_create_board_missing_name(client: FlaskClient) -> None:
    token, _ = _register(client)
    resp = client.post("/api/boards", json={}, headers=_auth(token))
    assert resp.status_code == 400
    assert _json(resp) == {"error": "Name is required"}


def test_create_board_success(client: FlaskClient) -> None:
    token, _ = _register(client)
    resp = client.post("/api/boards", json={"name": "My Board"}, headers=_auth(token))
    assert resp.status_code == 201
    body = _json(resp)
    assert set(body) == {"id", "name", "created_at"}
    assert body["name"] == "My Board"


def test_get_board_shape(client: FlaskClient) -> None:
    token, _ = _register(client)
    board_id = _create_board(client, token)
    resp = client.get(f"/api/boards/{board_id}", headers=_auth(token))
    assert resp.status_code == 200
    body = _json(resp)
    assert set(body) == {"board", "cards", "connections", "notes"}
    board = cast("dict[str, object]", body["board"])
    assert set(board) == {"id", "name", "share_token"}
    assert body["cards"] == []
    assert body["connections"] == []
    assert body["notes"] == []


def test_get_other_users_board_not_found(client: FlaskClient) -> None:
    owner_token, _ = _register(client)
    board_id = _create_board(client, owner_token)
    other_token, _ = _register(client)
    resp = client.get(f"/api/boards/{board_id}", headers=_auth(other_token))
    assert resp.status_code == 404
    assert _json(resp) == {"error": "Board not found"}


def test_rename_board_missing_name(client: FlaskClient) -> None:
    token, _ = _register(client)
    board_id = _create_board(client, token)
    resp = client.patch(f"/api/boards/{board_id}", json={}, headers=_auth(token))
    assert resp.status_code == 400
    assert _json(resp) == {"error": "Name is required"}


def test_rename_board_success(client: FlaskClient) -> None:
    token, _ = _register(client)
    board_id = _create_board(client, token)
    resp = client.patch(
        f"/api/boards/{board_id}", json={"name": "Renamed"}, headers=_auth(token)
    )
    assert resp.status_code == 200
    assert _json(resp) == {"id": board_id, "name": "Renamed"}


def test_rename_nonexistent_board(client: FlaskClient) -> None:
    token, _ = _register(client)
    resp = client.patch("/api/boards/999999", json={"name": "X"}, headers=_auth(token))
    assert resp.status_code == 404
    assert _json(resp) == {"error": "Board not found"}


def test_delete_board_success(client: FlaskClient) -> None:
    token, _ = _register(client)
    board_id = _create_board(client, token)
    resp = client.delete(f"/api/boards/{board_id}", headers=_auth(token))
    assert resp.status_code == 200
    assert _json(resp) == {"success": True}


# --------------------------------------------------------------------------- #
# Cards
# --------------------------------------------------------------------------- #


def test_create_card_missing_title(client: FlaskClient) -> None:
    token, _ = _register(client)
    board_id = _create_board(client, token)
    resp = client.post(
        f"/api/boards/{board_id}/cards",
        data={},
        content_type="multipart/form-data",
        headers=_auth(token),
    )
    assert resp.status_code == 400
    assert _json(resp) == {"error": "Title is required"}


def test_create_card_multipart_full(client: FlaskClient) -> None:
    token, _ = _register(client)
    board_id = _create_board(client, token)
    resp = client.post(
        f"/api/boards/{board_id}/cards",
        data={
            "title": "Card",
            "description": "Desc",
            "pos_x": "10",
            "pos_y": "20",
            "pin_position": "left",
            "inactive": "true",
            "color": "#f5e6c8",
        },
        content_type="multipart/form-data",
        headers=_auth(token),
    )
    assert resp.status_code == 201
    body = _json(resp)
    assert set(body) == {
        "id",
        "title",
        "description",
        "image_path",
        "pos_x",
        "pos_y",
        "pin_position",
        "inactive",
        "color",
    }
    assert body["title"] == "Card"
    assert body["description"] == "Desc"
    assert body["image_path"] is None
    assert body["pos_x"] == 10.0
    assert body["pos_y"] == 20.0
    assert body["pin_position"] == "left"
    assert body["inactive"] is True
    assert body["color"] == "#f5e6c8"


def test_create_card_bad_image_extension(client: FlaskClient) -> None:
    token, _ = _register(client)
    board_id = _create_board(client, token)
    resp = client.post(
        f"/api/boards/{board_id}/cards",
        data={"title": "Card", "image": (io.BytesIO(b"data"), "bad.gif")},
        content_type="multipart/form-data",
        headers=_auth(token),
    )
    assert resp.status_code == 400
    assert _json(resp) == {"error": "Only jpg/png images are accepted"}


def test_update_card_json_pos_x(client: FlaskClient) -> None:
    token, _ = _register(client)
    board_id = _create_board(client, token)
    card_id = _create_card(client, token, board_id)
    resp = client.put(
        f"/api/cards/{card_id}", json={"pos_x": 123.5}, headers=_auth(token)
    )
    assert resp.status_code == 200
    assert _json(resp)["pos_x"] == 123.5


def test_update_card_empty_json(client: FlaskClient) -> None:
    token, _ = _register(client)
    board_id = _create_board(client, token)
    card_id = _create_card(client, token, board_id)
    resp = client.put(f"/api/cards/{card_id}", json={}, headers=_auth(token))
    assert resp.status_code == 400
    assert _json(resp) == {"error": "Nothing to update"}


def test_update_card_multipart(client: FlaskClient) -> None:
    token, _ = _register(client)
    board_id = _create_board(client, token)
    card_id = _create_card(client, token, board_id)
    resp = client.put(
        f"/api/cards/{card_id}",
        data={
            "title": "Updated",
            "description": "New desc",
            "pin_position": "right",
            "inactive": "true",
            "color": "#d5e8d0",
        },
        content_type="multipart/form-data",
        headers=_auth(token),
    )
    assert resp.status_code == 200
    body = _json(resp)
    assert body["title"] == "Updated"
    assert body["description"] == "New desc"
    assert body["pin_position"] == "right"
    assert body["inactive"] is True
    assert body["color"] == "#d5e8d0"


def test_delete_card_success(client: FlaskClient) -> None:
    token, _ = _register(client)
    board_id = _create_board(client, token)
    card_id = _create_card(client, token, board_id)
    resp = client.delete(f"/api/cards/{card_id}", headers=_auth(token))
    assert resp.status_code == 200
    assert _json(resp) == {"success": True}


def test_delete_nonexistent_card(client: FlaskClient) -> None:
    token, _ = _register(client)
    resp = client.delete("/api/cards/999999", headers=_auth(token))
    assert resp.status_code == 404
    assert _json(resp) == {"error": "Card not found"}


def test_oversized_card_upload_returns_413(client: FlaskClient) -> None:
    token, _ = _register(client)
    board_id = _create_board(client, token)
    payload = b"x" * (MAX_IMAGE_BYTES + MAX_MULTIPART_OVERHEAD_BYTES + 1)
    resp = client.post(
        f"/api/boards/{board_id}/cards",
        data={"title": "Big", "image": (io.BytesIO(payload), "big.png")},
        content_type="multipart/form-data",
        headers=_auth(token),
    )
    assert resp.status_code == 413
    assert _json(resp) == {"error": UPLOAD_TOO_LARGE_MESSAGE}


# --------------------------------------------------------------------------- #
# Notes
# --------------------------------------------------------------------------- #


def test_create_note_success(client: FlaskClient) -> None:
    token, _ = _register(client)
    board_id = _create_board(client, token)
    resp = client.post(
        f"/api/boards/{board_id}/notes",
        json={"content": "Remember this"},
        headers=_auth(token),
    )
    assert resp.status_code == 201
    body = _json(resp)
    assert set(body) == {"id", "content", "pos_x", "pos_y"}
    assert body["content"] == "Remember this"


def test_update_note_content(client: FlaskClient) -> None:
    token, _ = _register(client)
    board_id = _create_board(client, token)
    note_id = _create_note(client, token, board_id)
    resp = client.put(
        f"/api/notes/{note_id}", json={"content": "Updated"}, headers=_auth(token)
    )
    assert resp.status_code == 200
    assert _json(resp)["content"] == "Updated"


def test_update_note_empty_body(client: FlaskClient) -> None:
    token, _ = _register(client)
    board_id = _create_board(client, token)
    note_id = _create_note(client, token, board_id)
    resp = client.put(f"/api/notes/{note_id}", json={}, headers=_auth(token))
    assert resp.status_code == 400
    assert _json(resp) == {"error": "Niente da aggiornare"}


def test_delete_note_success(client: FlaskClient) -> None:
    token, _ = _register(client)
    board_id = _create_board(client, token)
    note_id = _create_note(client, token, board_id)
    resp = client.delete(f"/api/notes/{note_id}", headers=_auth(token))
    assert resp.status_code == 200
    assert _json(resp) == {"success": True}


# --------------------------------------------------------------------------- #
# Connections
# --------------------------------------------------------------------------- #


def test_create_connection_missing_ids(client: FlaskClient) -> None:
    token, _ = _register(client)
    resp = client.post("/api/connections", json={}, headers=_auth(token))
    assert resp.status_code == 400
    assert _json(resp) == {"error": "Both card IDs are required"}


def test_create_connection_normalizes_card_ids(client: FlaskClient) -> None:
    token, _ = _register(client)
    board_id = _create_board(client, token)
    card_a = _create_card(client, token, board_id, "A")
    card_b = _create_card(client, token, board_id, "B")
    higher, lower = max(card_a, card_b), min(card_a, card_b)
    resp = client.post(
        "/api/connections",
        json={"card_id_1": higher, "card_id_2": lower},
        headers=_auth(token),
    )
    assert resp.status_code == 201
    body = _json(resp)
    id_1 = cast("int", body["card_id_1"])
    id_2 = cast("int", body["card_id_2"])
    assert id_1 < id_2
    assert {id_1, id_2} == {card_a, card_b}


def test_create_connection_duplicate(client: FlaskClient) -> None:
    token, _ = _register(client)
    board_id = _create_board(client, token)
    card_a = _create_card(client, token, board_id, "A")
    card_b = _create_card(client, token, board_id, "B")
    payload = {"card_id_1": card_a, "card_id_2": card_b}
    first = client.post("/api/connections", json=payload, headers=_auth(token))
    assert first.status_code == 201
    second = client.post("/api/connections", json=payload, headers=_auth(token))
    assert second.status_code == 409
    assert _json(second) == {"error": "Connection already exists"}


def test_create_connection_missing_card(client: FlaskClient) -> None:
    token, _ = _register(client)
    resp = client.post(
        "/api/connections",
        json={"card_id_1": 999999, "card_id_2": 999998},
        headers=_auth(token),
    )
    assert resp.status_code == 404
    assert _json(resp) == {"error": "Card not found"}


def test_delete_connection_success(client: FlaskClient) -> None:
    token, _ = _register(client)
    board_id = _create_board(client, token)
    card_a = _create_card(client, token, board_id, "A")
    card_b = _create_card(client, token, board_id, "B")
    created = client.post(
        "/api/connections",
        json={"card_id_1": card_a, "card_id_2": card_b},
        headers=_auth(token),
    )
    assert created.status_code == 201
    resp = client.delete(
        "/api/connections",
        json={"card_id_1": card_b, "card_id_2": card_a},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    assert _json(resp) == {"success": True}


# --------------------------------------------------------------------------- #
# Share
# --------------------------------------------------------------------------- #


def test_enable_share(client: FlaskClient) -> None:
    token, _ = _register(client)
    board_id = _create_board(client, token)
    resp = client.post(f"/api/boards/{board_id}/share", headers=_auth(token))
    assert resp.status_code == 200
    body = _json(resp)
    assert set(body) == {"share_token", "share_url"}
    share_token = cast("str", body["share_token"])
    assert share_token
    assert body["share_url"] == f"/share/{share_token}"


def test_get_shared_board_payload(client: FlaskClient) -> None:
    token, _ = _register(client)
    board_id = _create_board(client, token)
    card_a = _create_card(client, token, board_id, "A")
    card_b = _create_card(client, token, board_id, "B")
    _ = _create_note(client, token, board_id, "note")
    _ = client.post(
        "/api/connections",
        json={"card_id_1": card_a, "card_id_2": card_b},
        headers=_auth(token),
    )
    share_token = cast(
        "str",
        _json(client.post(f"/api/boards/{board_id}/share", headers=_auth(token)))[
            "share_token"
        ],
    )
    resp = client.get(f"/api/share/{share_token}")
    assert resp.status_code == 200
    body = _json(resp)
    assert set(body) == {"board", "cards", "connections", "notes"}
    assert len(cast("list[object]", body["cards"])) == 2
    assert len(cast("list[object]", body["connections"])) == 1
    assert len(cast("list[object]", body["notes"])) == 1


def test_get_shared_board_bogus_api(client: FlaskClient) -> None:
    resp = client.get("/api/share/bogus")
    assert resp.status_code == 404
    assert _json(resp) == {"error": "Board not found"}


def test_get_shared_board_bogus_page(client: FlaskClient) -> None:
    resp = client.get("/share/bogus")
    assert resp.status_code == 404
    assert resp.mimetype == "text/html"
    html = resp.get_data(as_text=True)
    assert "Board not found" in html
    assert "This board is no longer shared or the link is invalid." in html


def test_disable_share_invalidates_token(client: FlaskClient) -> None:
    token, _ = _register(client)
    board_id = _create_board(client, token)
    share_token = cast(
        "str",
        _json(client.post(f"/api/boards/{board_id}/share", headers=_auth(token)))[
            "share_token"
        ],
    )
    resp = client.delete(f"/api/boards/{board_id}/share", headers=_auth(token))
    assert resp.status_code == 200
    assert _json(resp) == {"ok": True}
    after = client.get(f"/api/share/{share_token}")
    assert after.status_code == 404
    assert _json(after) == {"error": "Board not found"}


# --------------------------------------------------------------------------- #
# Pages & static
# --------------------------------------------------------------------------- #


def test_home_page(client: FlaskClient) -> None:
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.mimetype == "text/html"


def test_board_page(client: FlaskClient) -> None:
    resp = client.get("/board")
    assert resp.status_code == 200
    assert resp.mimetype == "text/html"


def test_health(client: FlaskClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"message": "OK"}


def test_existing_asset_is_served(client: FlaskClient) -> None:
    resp = client.get("/assets/cork_background.jpg")
    assert resp.status_code == 200


def test_unknown_page_is_html_404(client: FlaskClient) -> None:
    resp = client.get("/does-not-exist")
    assert resp.status_code == 404
    assert resp.mimetype == "text/html"


# --------------------------------------------------------------------------- #
# Route snapshot
# --------------------------------------------------------------------------- #

_EXPECTED_ROUTES: set[tuple[tuple[str, ...], str]] = {
    (("GET", "HEAD", "OPTIONS"), "/"),
    (("OPTIONS", "POST"), "/api/auth/login"),
    (("GET", "HEAD", "OPTIONS"), "/api/auth/me"),
    (("OPTIONS", "POST"), "/api/auth/register"),
    (("GET", "HEAD", "OPTIONS"), "/api/boards"),
    (("OPTIONS", "POST"), "/api/boards"),
    (("DELETE", "OPTIONS"), "/api/boards/<int:board_id>"),
    (("GET", "HEAD", "OPTIONS"), "/api/boards/<int:board_id>"),
    (("OPTIONS", "PATCH"), "/api/boards/<int:board_id>"),
    (("OPTIONS", "POST"), "/api/boards/<int:board_id>/cards"),
    (("OPTIONS", "POST"), "/api/boards/<int:board_id>/notes"),
    (("DELETE", "OPTIONS"), "/api/boards/<int:board_id>/share"),
    (("OPTIONS", "POST"), "/api/boards/<int:board_id>/share"),
    (("DELETE", "OPTIONS"), "/api/cards/<int:card_id>"),
    (("OPTIONS", "PUT"), "/api/cards/<int:card_id>"),
    (("DELETE", "OPTIONS"), "/api/connections"),
    (("OPTIONS", "POST"), "/api/connections"),
    (("DELETE", "OPTIONS"), "/api/notes/<int:note_id>"),
    (("OPTIONS", "PUT"), "/api/notes/<int:note_id>"),
    (("GET", "HEAD", "OPTIONS"), "/api/share/<token>"),
    (("GET", "HEAD", "OPTIONS"), "/apple-touch-icon.png"),
    (("GET", "HEAD", "OPTIONS"), "/assets/<path:filename>"),
    (("GET", "HEAD", "OPTIONS"), "/board"),
    (("GET", "HEAD", "OPTIONS"), "/favicon.ico"),
    (("GET", "HEAD", "OPTIONS"), "/health"),
    (("GET", "HEAD", "OPTIONS"), "/robots.txt"),
    (("GET", "HEAD", "OPTIONS"), "/share/<token>"),
    (("GET", "HEAD", "OPTIONS"), "/site.webmanifest"),
    (("GET", "HEAD", "OPTIONS"), "/sitemap.xml"),
    (("GET", "HEAD", "OPTIONS"), "/static/<path:filename>"),
}


def test_route_snapshot_matches_head() -> None:
    from app import app

    actual = {
        (tuple(sorted(rule.methods or set())), rule.rule)
        for rule in app.url_map.iter_rules()
    }
    assert actual == _EXPECTED_ROUTES


# --------------------------------------------------------------------------- #
# Edge contracts (pinned CURRENT behavior, to be preserved by the refactor)
# --------------------------------------------------------------------------- #


def test_delete_connection_missing_ids_returns_500(
    error_client: FlaskClient,
) -> None:
    # Documents current behavior: both ids are None, so `id1 > id2` raises a
    # TypeError that surfaces as HTTP 500. This is a bug, but the refactor must
    # preserve the observable contract until a deliberate fix is made.
    token, _ = _register(error_client)
    resp = error_client.delete("/api/connections", json={}, headers=_auth(token))
    _assert_internal_server_error(resp)


def test_delete_connection_single_id_returns_500(
    error_client: FlaskClient,
) -> None:
    # Documents current behavior: comparing an int to None raises TypeError -> 500.
    token, _ = _register(error_client)
    resp = error_client.delete(
        "/api/connections", json={"card_id_1": 1}, headers=_auth(token)
    )
    _assert_internal_server_error(resp)


def test_create_connection_across_different_boards(client: FlaskClient) -> None:
    # Documents current behavior: there is no same-board validation, so two
    # cards living on different boards can be connected (201).
    token, _ = _register(client)
    board_a = _create_board(client, token, "A")
    board_b = _create_board(client, token, "B")
    card_a = _create_card(client, token, board_a, "A")
    card_b = _create_card(client, token, board_b, "B")
    resp = client.post(
        "/api/connections",
        json={"card_id_1": card_a, "card_id_2": card_b},
        headers=_auth(token),
    )
    assert resp.status_code == 201
    body = _json(resp)
    id_1 = cast("int", body["card_id_1"])
    id_2 = cast("int", body["card_id_2"])
    assert {id_1, id_2} == {card_a, card_b}


def test_create_connection_self_loop(client: FlaskClient) -> None:
    # Documents current behavior: the same card id twice is accepted (no
    # self-loop check) and the normalized pair keeps both ids equal.
    token, _ = _register(client)
    board_id = _create_board(client, token)
    card_id = _create_card(client, token, board_id)
    resp = client.post(
        "/api/connections",
        json={"card_id_1": card_id, "card_id_2": card_id},
        headers=_auth(token),
    )
    assert resp.status_code == 201
    body = _json(resp)
    assert body["card_id_1"] == card_id
    assert body["card_id_2"] == card_id


def test_delete_other_users_board_returns_success(client: FlaskClient) -> None:
    # Documents current behavior: DELETE is scoped by user_id but always returns
    # 200 {"success": true}, even when nothing was deleted.
    owner_token, _ = _register(client)
    board_id = _create_board(client, owner_token)
    other_token, _ = _register(client)
    resp = client.delete(f"/api/boards/{board_id}", headers=_auth(other_token))
    assert resp.status_code == 200
    assert _json(resp) == {"success": True}


def test_update_card_multipart_without_title(client: FlaskClient) -> None:
    token, _ = _register(client)
    board_id = _create_board(client, token)
    card_id = _create_card(client, token, board_id)
    resp = client.put(
        f"/api/cards/{card_id}",
        data={"description": "no title"},
        content_type="multipart/form-data",
        headers=_auth(token),
    )
    assert resp.status_code == 400
    assert _json(resp) == {"error": "Title is required"}


def test_update_other_users_note_not_found(client: FlaskClient) -> None:
    owner_token, _ = _register(client)
    board_id = _create_board(client, owner_token)
    note_id = _create_note(client, owner_token, board_id)
    other_token, _ = _register(client)
    resp = client.put(
        f"/api/notes/{note_id}", json={"content": "hack"}, headers=_auth(other_token)
    )
    assert resp.status_code == 404
    assert _json(resp) == {"error": "Note not found"}


def test_delete_other_users_note_not_found(client: FlaskClient) -> None:
    owner_token, _ = _register(client)
    board_id = _create_board(client, owner_token)
    note_id = _create_note(client, owner_token, board_id)
    other_token, _ = _register(client)
    resp = client.delete(f"/api/notes/{note_id}", headers=_auth(other_token))
    assert resp.status_code == 404
    assert _json(resp) == {"error": "Note not found"}


def test_update_other_users_card_not_found(client: FlaskClient) -> None:
    owner_token, _ = _register(client)
    board_id = _create_board(client, owner_token)
    card_id = _create_card(client, owner_token, board_id)
    other_token, _ = _register(client)
    resp = client.put(
        f"/api/cards/{card_id}", json={"pos_x": 1}, headers=_auth(other_token)
    )
    assert resp.status_code == 404
    assert _json(resp) == {"error": "Card not found"}


def test_delete_other_users_card_not_found(client: FlaskClient) -> None:
    owner_token, _ = _register(client)
    board_id = _create_board(client, owner_token)
    card_id = _create_card(client, owner_token, board_id)
    other_token, _ = _register(client)
    resp = client.delete(f"/api/cards/{card_id}", headers=_auth(other_token))
    assert resp.status_code == 404
    assert _json(resp) == {"error": "Card not found"}


def test_share_page_with_valid_token_returns_html(client: FlaskClient) -> None:
    token, _ = _register(client)
    board_id = _create_board(client, token)
    share_token = cast(
        "str",
        _json(client.post(f"/api/boards/{board_id}/share", headers=_auth(token)))[
            "share_token"
        ],
    )
    resp = client.get(f"/share/{share_token}")
    assert resp.status_code == 200
    assert resp.mimetype == "text/html"


def test_update_card_json_title_description_color(client: FlaskClient) -> None:
    token, _ = _register(client)
    board_id = _create_board(client, token)
    card_id = _create_card(client, token, board_id)
    resp = client.put(
        f"/api/cards/{card_id}",
        json={"title": "New title", "description": "New desc", "color": "#d5e8d0"},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    body = _json(resp)
    assert body["title"] == "New title"
    assert body["description"] == "New desc"
    assert body["color"] == "#d5e8d0"


def test_create_card_invalid_color_falls_back_to_null(client: FlaskClient) -> None:
    token, _ = _register(client)
    board_id = _create_board(client, token)
    resp = client.post(
        f"/api/boards/{board_id}/cards",
        data={"title": "Card", "color": "#000000"},
        content_type="multipart/form-data",
        headers=_auth(token),
    )
    assert resp.status_code == 201
    assert _json(resp)["color"] is None


def test_update_card_invalid_color_falls_back_to_null(client: FlaskClient) -> None:
    token, _ = _register(client)
    board_id = _create_board(client, token)
    card_id = _create_card(client, token, board_id)
    resp = client.put(
        f"/api/cards/{card_id}",
        data={"title": "Card", "color": "#000000"},
        content_type="multipart/form-data",
        headers=_auth(token),
    )
    assert resp.status_code == 200
    assert _json(resp)["color"] is None


def test_me_expired_token(client: FlaskClient) -> None:
    expired = pyjwt.encode(
        {
            "user_id": 1,
            "exp": datetime.now(timezone.utc) - timedelta(seconds=5),
        },
        SECRET_KEY,
        algorithm="HS256",
    )
    resp = client.get("/api/auth/me", headers=_auth(expired))
    assert resp.status_code == 401
    assert _json(resp) == {"error": "Token expired"}


def test_create_note_non_numeric_pos_x_returns_500(
    error_client: FlaskClient,
) -> None:
    # Documents current behavior: float("not-a-number") raises a ValueError
    # inside the view, surfacing as HTTP 500. Preserve until deliberately fixed.
    token, _ = _register(error_client)
    board_id = _create_board(error_client, token)
    resp = error_client.post(
        f"/api/boards/{board_id}/notes",
        json={"content": "x", "pos_x": "not-a-number"},
        headers=_auth(token),
    )
    _assert_internal_server_error(resp)
