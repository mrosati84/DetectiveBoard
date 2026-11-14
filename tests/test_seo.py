"""Search-engine and social preview metadata served by the pages blueprint."""

import html as html_lib
import json
import re
import uuid
import xml.etree.ElementTree as ET
from typing import cast

import pytest
from flask.testing import FlaskClient

from app import app
from detectiveboard.content import CONTENT_PAGES, HOME_FAQ

SITE_URL: str = cast("str", app.config["SITE_URL"])

INDEXABLE_PATHS = [
    "/",
    "/detective-board-template",
    "/guides/",
    "/guides/how-to-make-a-detective-board",
]
CONTENT_PATHS = [page.path for page in CONTENT_PAGES]
SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def _ld_json_blocks(html: str) -> list[dict[str, object]]:
    blocks = re.findall(
        r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL
    )
    return [cast("dict[str, object]", json.loads(block)) for block in blocks]


def _ld_json(html: str) -> dict[str, object]:
    blocks = _ld_json_blocks(html)
    assert blocks, "expected a JSON-LD block"
    return blocks[0]


def _graph_node(html: str, node_type: str) -> dict[str, object]:
    graph = cast("list[dict[str, object]]", _ld_json(html)["@graph"])
    return next(node for node in graph if node["@type"] == node_type)


def _text_of(html: str, tag: str) -> str:
    match = re.search(rf"<{tag}\b[^>]*>(.*?)</{tag}>", html, re.DOTALL)
    assert match is not None, f"expected a <{tag}>"
    return html_lib.unescape(re.sub(r"<[^>]+>", "", match.group(1))).strip()


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


def test_sitemap_lists_exactly_the_indexable_pages(client: FlaskClient) -> None:
    root = ET.fromstring(client.get("/sitemap.xml").get_data())
    locs = [loc.text for loc in root.findall("sm:url/sm:loc", SITEMAP_NS)]
    assert sorted(cast("list[str]", locs)) == sorted(
        f"{SITE_URL}{path}" for path in INDEXABLE_PATHS
    )


@pytest.mark.parametrize("path", CONTENT_PATHS)
def test_content_pages_are_served(client: FlaskClient, path: str) -> None:
    resp = client.get(path)
    assert resp.status_code == 200
    assert resp.mimetype == "text/html"


@pytest.mark.parametrize("path", INDEXABLE_PATHS)
def test_indexable_pages_have_robots_and_canonical(
    client: FlaskClient, path: str
) -> None:
    html = client.get(path).get_data(as_text=True)
    assert '<meta name="robots" content="index, follow' in html
    canonicals = re.findall(r'<link rel="canonical" href="([^"]+)">', html)
    assert canonicals == [f"{SITE_URL}{path}"]


@pytest.mark.parametrize("path", INDEXABLE_PATHS)
def test_indexable_pages_have_unique_title_and_description(
    client: FlaskClient, path: str
) -> None:
    html = client.get(path).get_data(as_text=True)
    assert "detective board" in _text_of(html, "title").lower()
    assert "detective board" in _text_of(html, "h1").lower()
    assert re.search(r'<meta name="description" content="[^"]{50,}">', html)


def test_indexable_pages_have_distinct_titles(client: FlaskClient) -> None:
    titles = [
        _text_of(client.get(path).get_data(as_text=True), "title")
        for path in INDEXABLE_PATHS
    ]
    assert len(set(titles)) == len(titles)


@pytest.mark.parametrize("path", INDEXABLE_PATHS)
def test_indexable_pages_json_ld_is_valid(client: FlaskClient, path: str) -> None:
    blocks = _ld_json_blocks(client.get(path).get_data(as_text=True))
    assert blocks
    for block in blocks:
        assert block["@context"] == "https://schema.org"


@pytest.mark.parametrize("path", INDEXABLE_PATHS)
def test_public_pages_share_footer_links_and_auth_modals(
    client: FlaskClient, path: str
) -> None:
    html = client.get(path).get_data(as_text=True)
    assert 'id="home-footer"' in html
    assert 'href="/detective-board-template">Templates</a>' in html
    assert 'href="/guides/">Guides</a>' in html
    assert 'id="login-modal-overlay"' in html
    assert 'id="register-modal-overlay"' in html


def test_unknown_page_is_not_indexed(client: FlaskClient) -> None:
    resp = client.get("/does-not-exist")
    assert resp.status_code == 404
    html = resp.get_data(as_text=True)
    assert '<meta name="robots" content="noindex, follow">' in html
    assert 'rel="canonical"' not in html


def test_missing_share_page_is_not_indexed(client: FlaskClient) -> None:
    resp = client.get("/share/does-not-exist")
    assert resp.status_code == 404
    assert '<meta name="robots" content="noindex, follow">' in resp.get_data(
        as_text=True
    )


def test_shared_board_page_is_not_indexed(client: FlaskClient) -> None:
    username = f"seo_{uuid.uuid4().hex[:12]}"
    token = cast(
        "str",
        client.post(
            "/api/auth/register",
            json={"username": username, "password": "password123"},
        ).get_json()["token"],
    )
    headers = {"Authorization": f"Bearer {token}"}
    board_id = client.post("/api/boards", json={"name": "B"}, headers=headers).get_json()[
        "id"
    ]
    share_token = client.post(
        f"/api/boards/{board_id}/share", headers=headers
    ).get_json()["share_token"]

    resp = client.get(f"/share/{share_token}")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert '<meta name="robots" content="noindex, follow">' in html
    assert 'rel="canonical"' not in html


def test_home_targets_detective_board_keyword(client: FlaskClient) -> None:
    html = client.get("/").get_data(as_text=True)
    assert "detective board" in _text_of(html, "title").lower()
    assert _text_of(html, "h1") == "The free online detective board"
    assert "red string" in html
    # The brand stays one word in the logo.
    assert "<span>DetectiveBoard</span>" in html


def test_home_faq_structured_data_mirrors_visible_faq(client: FlaskClient) -> None:
    html = client.get("/").get_data(as_text=True)
    faq = _graph_node(html, "FAQPage")
    entities = cast("list[dict[str, object]]", faq["mainEntity"])
    visible = [
        html_lib.unescape(q) for q in re.findall(r"<summary>(.*?)</summary>", html)
    ]
    assert [e["name"] for e in entities] == visible
    assert visible == [entry.question for entry in HOME_FAQ]
    assert visible[0] == "What is a detective board?"
    for entity, entry in zip(entities, HOME_FAQ, strict=True):
        answer = cast("dict[str, object]", entity["acceptedAnswer"])
        assert answer["text"] == str(entry.answer)
        assert f"<p>{entry.answer}</p>" in html


def test_home_links_to_content_pages(client: FlaskClient) -> None:
    main = client.get("/").get_data(as_text=True).split("<main>")[1].split("</main>")[0]
    assert 'href="/detective-board-template"' in main
    assert 'href="/guides/how-to-make-a-detective-board"' in main


def test_guide_declares_article_and_breadcrumbs(client: FlaskClient) -> None:
    path = "/guides/how-to-make-a-detective-board"
    html = client.get(path).get_data(as_text=True)
    article = _graph_node(html, "Article")
    assert article["headline"] == "How to make a detective board"
    assert article["mainEntityOfPage"] == f"{SITE_URL}{path}"
    assert "datePublished" in article and "dateModified" in article

    breadcrumbs = _graph_node(html, "BreadcrumbList")
    items = cast("list[dict[str, object]]", breadcrumbs["itemListElement"])
    assert [item["item"] for item in items] == [
        f"{SITE_URL}/",
        f"{SITE_URL}/guides/",
        f"{SITE_URL}{path}",
    ]
    assert [item["position"] for item in items] == [1, 2, 3]


def test_guides_index_lists_every_guide(client: FlaskClient) -> None:
    html = client.get("/guides/").get_data(as_text=True)
    guide_paths = [page.path for page in CONTENT_PAGES if page.kind == "guide"]
    assert guide_paths
    for guide_path in guide_paths:
        assert f'href="{guide_path}"' in html


def test_template_page_shows_example_boards_with_signup_ctas(
    client: FlaskClient,
) -> None:
    html = client.get("/detective-board-template").get_data(as_text=True)
    assert html.count('class="template-case"') == 4
    assert html.count("Start this board") == 4
    assert 'onclick="openRegisterModal()"' in html


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
