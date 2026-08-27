from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from tests.integration.support.logging import log_expected_actual, log_header
from tests.ui._support import full_stack_enabled
from tests.ui.api._support import open_resource, open_search

# The bits every API page shares: stylesheet, logo, header links.
#
# Worth checking in a browser because a missing stylesheet still returns 200 --
# the page just loses all its styling, which a status check would never notice.
def collect_responses(page: Page) -> list[tuple[str, int]]:
    """Record every response the page makes.

    page_signals only tracks 5xx; a missing stylesheet is a 404 and would
    otherwise pass unnoticed behind a 200 page.
    """
    seen: list[tuple[str, int]] = []
    page.on("response", lambda response: seen.append((response.url, response.status)))
    return seen


pytestmark = pytest.mark.skipif(
    not full_stack_enabled(),
    reason="API view tests require the full stack (Nginx + API)",
)


# ==============================================================================
# The stylesheet loads. If its path breaks the page still returns 200, just
# unstyled.
# ------------------------------------------------------------------------------
def test_search_view_stylesheet_loads(page: Page, api_base_url: str, ui_timeout_ms: int):
    log_header("API views load their stylesheet")
    responses = collect_responses(page)
    open_search(page, api_base_url, ui_timeout_ms)
    # domcontentloaded fires while subresources are still in flight; wait for
    # the stylesheet response to land before inspecting the log.
    page.wait_for_load_state("load", timeout=ui_timeout_ms)

    stylesheets = [(url, status) for url, status in responses if "bluecore.css" in url]
    log_expected_actual("bluecore.css responses", "one, status 200", stylesheets)
    assert stylesheets, (
        f"The page requested no bluecore.css. Responses seen: {[u for u, _ in responses]}"
    )
    for url, status in stylesheets:
        assert status == 200, f"Stylesheet {url} returned {status}, so the view is unstyled."


# ==============================================================================
# Same check on a record page, which people often reach directly.
# ------------------------------------------------------------------------------
def test_resource_view_stylesheet_loads(
    page: Page,
    api_base_url: str,
    seeded_resource_uuids: tuple[str, str],
    ui_timeout_ms: int,
):
    log_header("API resource view loads its stylesheet")
    work_uuid, _ = seeded_resource_uuids
    responses = collect_responses(page)
    open_resource(page, api_base_url, "works", work_uuid, ui_timeout_ms)
    page.wait_for_load_state("load", timeout=ui_timeout_ms)

    stylesheets = [(url, status) for url, status in responses if "bluecore.css" in url]
    assert stylesheets, "The resource view requested no stylesheet."
    for url, status in stylesheets:
        assert status == 200, f"Stylesheet {url} returned {status}."


# ==============================================================================
# Header links are absolute URLs. The brand link falls back to production when
# BLUECORE_URL is unset, so a local page can quietly point at prod.
# ------------------------------------------------------------------------------
def test_header_links_are_absolute(page: Page, api_base_url: str, ui_timeout_ms: int):
    log_header("API view header links are absolute")
    open_search(page, api_base_url, ui_timeout_ms)

    brand_href = page.locator("a.bc-brand").get_attribute("href")
    log_expected_actual("brand link", "absolute http(s) URL", brand_href)
    assert brand_href and brand_href.startswith(("http://", "https://")), brand_href

    nav_links = page.locator("nav.bc-nav a")
    expect(nav_links).to_have_count(2)
    for index in range(nav_links.count()):
        href = nav_links.nth(index).get_attribute("href")
        assert href and href.startswith(("http://", "https://")), (
            f"Nav link {index} has a non-absolute href: {href!r}"
        )


# ==============================================================================
# The logo loads rather than showing as a broken image.
# ------------------------------------------------------------------------------
def test_brand_logo_loads(page: Page, api_base_url: str, ui_timeout_ms: int):
    log_header("API view brand logo loads")
    responses = collect_responses(page)
    open_search(page, api_base_url, ui_timeout_ms)
    page.wait_for_load_state("load", timeout=ui_timeout_ms)

    logos = [(url, status) for url, status in responses if "blue-core-logo" in url]
    log_expected_actual("logo responses", "one, status 200", logos)
    assert logos, "The header requested no logo image."
    for url, status in logos:
        assert status == 200, f"Logo {url} returned {status}."


# ==============================================================================
# Both pages load with no browser errors and no 500s.
# ------------------------------------------------------------------------------
def test_search_view_loads_without_errors(
    page: Page, page_signals, api_base_url: str, ui_timeout_ms: int
):
    log_header("API search view loads without errors")
    open_search(page, api_base_url, ui_timeout_ms)
    page.wait_for_load_state("networkidle", timeout=ui_timeout_ms)

    log_expected_actual("page errors", [], page_signals.page_errors)
    log_expected_actual("server (5xx) responses", [], page_signals.server_errors)
    assert not page_signals.page_errors, page_signals.page_errors
    assert not page_signals.server_errors, page_signals.server_errors


def test_resource_view_loads_without_errors(
    page: Page,
    page_signals,
    api_base_url: str,
    seeded_resource_uuids: tuple[str, str],
    ui_timeout_ms: int,
):
    log_header("API resource view loads without errors")
    work_uuid, _ = seeded_resource_uuids
    open_resource(page, api_base_url, "works", work_uuid, ui_timeout_ms)
    page.wait_for_load_state("networkidle", timeout=ui_timeout_ms)

    log_expected_actual("page errors", [], page_signals.page_errors)
    log_expected_actual("server (5xx) responses", [], page_signals.server_errors)
    assert not page_signals.page_errors, page_signals.page_errors
    assert not page_signals.server_errors, page_signals.server_errors
