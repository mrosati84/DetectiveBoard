"""Search-engine and social preview metadata served by the pages blueprint."""

import json
import re
from typing import cast

from flask.testing import FlaskClient

from app import app

SITE_URL: str = cast("str", app.config["SITE_URL"])


def _ld_json(html: str) -> dict[str, object]:
    match = re.search(
        r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL
    )
    assert match is not None, "expected a JSON-LD block"
    return cast("dict[str, object]", json.loads(match.group(1)))


def test_home_is_indexable_with_canonical(client: FlaskClient) -> None:
    html = client.get("/").get_data(as_text=True)
    assert '<meta name="robots" content="index, follow' in html
    assert f'<link rel="canonical" href="{SITE_URL}/">' in html
    assert '<meta property="og:site_name" content="DetectiveBoard">' in html
    assert f'content="{SITE_URL}/static/img/og-image.jpg"' in html


def test_home_declares_website_structured_data(client: FlaskClient) -> None:
    data = _ld_json(client.get("/").get_data(as_text=True))
    graph = cast("list[dict[str, object]]", data["@graph"])
    website = next(node for node in graph if node["@type"] == "WebSite")
    assert website["name"] == "DetectiveBoard"
    assert website["url"] == f"{SITE_URL}/"


def test_app_pages_are_not_indexed(client: FlaskClient) -> None:
    html = client.get("/board").get_data(as_text=True)
    assert '<meta name="robots" content="noindex, follow">' in html
    assert 'rel="canonical"' not in html


def test_favicon_is_served(client: FlaskClient) -> None:
    resp = client.get("/favicon.ico")
    assert resp.status_code == 200
    assert resp.mimetype == "image/x-icon"


def test_apple_touch_icon_is_served(client: FlaskClient) -> None:
    resp = client.get("/apple-touch-icon.png")
    assert resp.status_code == 200
    assert resp.mimetype == "image/png"


def test_robots_txt(client: FlaskClient) -> None:
    resp = client.get("/robots.txt")
    assert resp.status_code == 200
    assert resp.mimetype == "text/plain"
    body = resp.get_data(as_text=True)
    assert "Disallow: /api/" in body
    assert f"Sitemap: {SITE_URL}/sitemap.xml" in body


def test_sitemap_xml(client: FlaskClient) -> None:
    resp = client.get("/sitemap.xml")
    assert resp.status_code == 200
    assert resp.mimetype == "application/xml"
    assert f"<loc>{SITE_URL}/</loc>" in resp.get_data(as_text=True)


def test_web_manifest(client: FlaskClient) -> None:
    resp = client.get("/site.webmanifest")
    assert resp.status_code == 200
    manifest = cast("dict[str, object]", json.loads(resp.get_data(as_text=True)))
    assert manifest["name"] == "DetectiveBoard"


def test_www_get_redirects_permanently_to_apex(client: FlaskClient) -> None:
    resp = client.get("/share/abc?x=1", base_url="http://www.example.com")
    assert resp.status_code == 301
    assert resp.headers["Location"] == "https://example.com/share/abc?x=1"


def test_www_post_redirect_preserves_method(client: FlaskClient) -> None:
    resp = client.post("/api/boards", base_url="http://www.example.com")
    assert resp.status_code == 308
    assert resp.headers["Location"] == "https://example.com/api/boards"


def test_www_forwarded_host_redirects_to_apex(client: FlaskClient) -> None:
    resp = client.get(
        "/",
        base_url="http://internal.example.net",
        headers={"X-Forwarded-Host": "www.example.com"},
    )
    assert resp.status_code == 301
    assert resp.headers["Location"] == "https://example.com/"


def test_apex_host_is_not_redirected(client: FlaskClient) -> None:
    resp = client.get("/health", base_url="http://example.com")
    assert resp.status_code == 200
