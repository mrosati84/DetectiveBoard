"""Board export (issue #6): page wiring and vendored static assets."""

import pytest
from flask.testing import FlaskClient

VENDOR_SCRIPTS = (
    "/static/js/vendor/html-to-image-1.11.11.js",
    "/static/js/vendor/jspdf-2.5.2.umd.min.js",
)
FONT_FILES = (
    "/static/fonts/caveat-latin-400-normal.woff2",
    "/static/fonts/caveat-latin-600-normal.woff2",
    "/static/fonts/caveat-latin-ext-400-normal.woff2",
    "/static/fonts/caveat-latin-ext-600-normal.woff2",
)


def test_board_page_loads_vendor_scripts_before_export_js(client: FlaskClient) -> None:
    html = client.get("/board").get_data(as_text=True)
    positions = [html.index(f'src="{src}"') for src in VENDOR_SCRIPTS]
    board_js = html.index('src="/static/js/board.js"')
    export_js = html.index('src="/static/js/export.js"')
    assert max(positions) < board_js < export_js


def test_board_page_has_export_button_and_modal(client: FlaskClient) -> None:
    html = client.get("/board").get_data(as_text=True)
    assert 'id="export-btn"' in html
    assert 'id="export-modal-overlay"' in html
    for fmt in ("png", "pdf", "svg"):
        assert f'name="export_format" value="{fmt}"' in html
    assert 'id="export-include-background" checked' in html
    assert 'id="export-download-btn"' in html
    assert 'id="export-form-error"' in html


def test_export_is_not_offered_on_other_pages(client: FlaskClient) -> None:
    html = client.get("/").get_data(as_text=True)
    assert "export.js" not in html
    assert "html-to-image" not in html
    assert "jspdf" not in html


def test_google_fonts_replaced_by_self_hosted_caveat(client: FlaskClient) -> None:
    for path in ("/", "/board"):
        html = client.get(path).get_data(as_text=True)
        assert "fonts.googleapis.com" not in html
        assert "fonts.gstatic.com" not in html
        assert 'href="/static/css/fonts.css"' in html


@pytest.mark.parametrize("path", [*VENDOR_SCRIPTS, "/static/js/export.js"])
def test_scripts_are_served(client: FlaskClient, path: str) -> None:
    resp = client.get(path)
    assert resp.status_code == 200
    assert "javascript" in resp.mimetype
    assert len(resp.get_data()) > 0


@pytest.mark.parametrize("path", FONT_FILES)
def test_fonts_are_served(client: FlaskClient, path: str) -> None:
    resp = client.get(path)
    assert resp.status_code == 200
    assert resp.mimetype == "font/woff2"
    assert resp.get_data()[:4] == b"wOF2"


def test_font_stylesheet_declares_caveat(client: FlaskClient) -> None:
    resp = client.get("/static/css/fonts.css")
    assert resp.status_code == 200
    css = resp.get_data(as_text=True)
    assert "font-family: 'Caveat'" in css
    for font in FONT_FILES:
        assert f"url('../fonts/{font.rsplit('/', 1)[1]}')" in css


@pytest.mark.parametrize(
    "path",
    [
        "/static/js/vendor/html-to-image.LICENSE",
        "/static/js/vendor/jspdf.LICENSE",
        "/static/fonts/OFL.txt",
    ],
)
def test_third_party_licenses_are_present(client: FlaskClient, path: str) -> None:
    assert client.get(path).status_code == 200
