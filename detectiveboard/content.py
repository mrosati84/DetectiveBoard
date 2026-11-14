"""Static marketing content: the indexable page registry and homepage FAQ.

``CONTENT_PAGES`` is the single source of truth for the static, indexable
pages served by the content blueprint. The sitemap is generated from
``indexable_pages()`` so a page added here is routed and listed in one place.
"""

from dataclasses import dataclass
from datetime import date
from typing import Literal

from markupsafe import Markup

PageKind = Literal["home", "landing", "index", "guide"]


@dataclass(frozen=True)
class ContentPage:
    """A static, indexable page.

    ``name`` is short link text used in breadcrumbs, the footer and the guides
    index; each template still defines its own ``<title>`` and description.
    """

    path: str
    endpoint: str
    template: str
    kind: PageKind
    name: str
    summary: str
    published: date | None = None
    updated: date | None = None


HOME_PAGE = ContentPage(
    path="/",
    endpoint="pages.home",
    template="home.html",
    kind="home",
    name="Home",
    summary="The free online detective board.",
)

CONTENT_PAGES: tuple[ContentPage, ...] = (
    ContentPage(
        path="/detective-board-template",
        endpoint="content.detective_board_template",
        template="content/detective_board_template.html",
        kind="landing",
        name="Detective board templates",
        summary=(
            "Four example detective boards — murder mystery, true crime, novel "
            "plot and RPG campaign — to copy for your own case."
        ),
    ),
    ContentPage(
        path="/guides/",
        endpoint="content.guides_index",
        template="content/guides_index.html",
        kind="index",
        name="Guides",
        summary="Guides to building and using a detective board.",
    ),
    ContentPage(
        path="/guides/how-to-make-a-detective-board",
        endpoint="content.how_to_make_a_detective_board",
        template="content/guides/how_to_make_a_detective_board.html",
        kind="guide",
        name="How to make a detective board",
        summary=(
            "Build a detective board step by step: the classic cork board with "
            "pins and red string, and the faster online version."
        ),
        published=date(2026, 11, 14),
        updated=date(2026, 11, 14),
    ),
)


def indexable_pages() -> tuple[ContentPage, ...]:
    """Every page that should be indexed and listed in the sitemap."""
    return (HOME_PAGE, *CONTENT_PAGES)


def guides() -> tuple[ContentPage, ...]:
    return tuple(page for page in CONTENT_PAGES if page.kind == "guide")


def page_for(endpoint: str) -> ContentPage:
    return next(page for page in indexable_pages() if page.endpoint == endpoint)


@dataclass(frozen=True)
class FaqEntry:
    """A question shown on the homepage and mirrored in ``FAQPage`` JSON-LD."""

    question: str
    answer: Markup


HOME_FAQ: tuple[FaqEntry, ...] = (
    FaqEntry(
        question="What is a detective board?",
        answer=Markup(
            "A detective board is a cork board where investigators pin photos, "
            "notes and clues, then connect related items with red string to "
            "reveal patterns. You may also know it as an investigation board, "
            "evidence board, suspect board, crime board or conspiracy board. "
            "DetectiveBoard is the online version: the same cork board and red "
            "string, without the pins in your fingers."
        ),
    ),
    FaqEntry(
        question="Is it really free?",
        answer=Markup(
            "Yes. DetectiveBoard is free to use, with no ads and no premium tier."
        ),
    ),
    FaqEntry(
        question="Do I need a template to get started?",
        answer=Markup(
            "No — a blank board is all you need. If you want inspiration, browse "
            'our <a href="/detective-board-template">detective board templates</a> '
            "for a murder mystery, a true crime case, a novel plot and an RPG "
            "campaign."
        ),
    ),
    FaqEntry(
        question="What about my privacy?",
        answer=Markup(
            "Your boards are private to your account. We don’t use cookies or "
            "ads; we only keep anonymous, aggregate visit counts so we know the "
            "site is being used."
        ),
    ),
    FaqEntry(
        question="Can other people see my boards?",
        answer=Markup(
            "Only if you share one. Sharing creates a read-only link that you "
            "can disable at any time."
        ),
    ),
    FaqEntry(
        question="Does it work on my phone?",
        answer=Markup(
            "DetectiveBoard runs in any modern browser, though a bigger screen "
            "gives your investigation more room to breathe."
        ),
    ),
)
