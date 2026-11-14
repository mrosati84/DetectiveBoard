"""Static, indexable marketing pages (templates landing page and guides).

Routes are generated from ``detectiveboard.content.CONTENT_PAGES`` so that the
same list feeds both routing and the sitemap.
"""

from collections.abc import Callable

from flask import Blueprint, render_template

from detectiveboard.content import (
    CONTENT_PAGES,
    HOME_PAGE,
    ContentPage,
    guides,
    page_for,
)

bp = Blueprint("content", __name__)


def breadcrumbs_for(page: ContentPage) -> list[ContentPage]:
    """Trail from the homepage down to ``page`` (inclusive)."""
    trail = [HOME_PAGE]
    if page.kind == "guide":
        trail.append(page_for("content.guides_index"))
    trail.append(page)
    return trail


def _make_view(page: ContentPage) -> Callable[[], str]:
    def view() -> str:
        return render_template(
            page.template,
            page=page,
            breadcrumbs=breadcrumbs_for(page),
            guides=guides(),
        )

    return view


for _page in CONTENT_PAGES:
    _blueprint_name, _, _view_name = _page.endpoint.partition(".")
    assert _blueprint_name == bp.name, _page.endpoint
    bp.add_url_rule(_page.path, endpoint=_view_name, view_func=_make_view(_page))
