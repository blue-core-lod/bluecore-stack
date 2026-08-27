from __future__ import annotations

from urllib.parse import urlparse

import pytest
from playwright.sync_api import Page, expect

from tests.integration.support.logging import log_expected_actual, log_header
from tests.ui._support import full_stack_enabled
from tests.ui.landing._support import (
    FOOTER_LINKS,
    MOBILE_VIEWPORT,
    PAGE_ASSETS,
    SERVICE_ROWS,
    collect_responses,
    open_landing,
    row_locator,
)

# The landing page at /, the front door to the stack, which nothing else in the
# suite requests. The live status badge is in test_landing_health.py.
pytestmark = pytest.mark.skipif(
    not full_stack_enabled(),
    reason="Landing page tests require the full stack (Nginx)",
)


# ==============================================================================
# The page renders its title, brand and lead line.
# ------------------------------------------------------------------------------
def test_landing_renders_page_shell(page: Page, landing_base_url: str, ui_timeout_ms: int):
    log_header("Landing page renders its shell")
    open_landing(page, landing_base_url, ui_timeout_ms)

    log_expected_actual("page title", "Blue Core · API & Workflows", page.title())
    expect(page).to_have_title("Blue Core · API & Workflows")
    expect(page.locator("header.site-header")).to_be_visible()
    expect(page.locator("p.lead")).to_have_text("API, identity, workflows, and tools.")
    expect(page.locator("span.brand-sub")).to_have_text("Platform")


# ==============================================================================
# Stylesheet, script and logo all load. A missing one still returns 200, just
# unstyled or dead.
# ------------------------------------------------------------------------------
def test_landing_assets_load(page: Page, landing_base_url: str, ui_timeout_ms: int):
    log_header("Landing page assets load")
    responses = collect_responses(page)
    open_landing(page, landing_base_url, ui_timeout_ms)
    page.wait_for_load_state("load", timeout=ui_timeout_ms)

    for asset in PAGE_ASSETS:
        matches = [(url, status) for url, status in responses if asset in url]
        log_expected_actual(f"{asset} response", "200", matches)
        assert matches, f"The page never requested {asset}."
        for url, status in matches:
            assert status == 200, f"{url} returned {status}."

    # The logo must actually decode, not just download.
    logo = page.locator("img.logo")
    expect(logo).to_be_visible()
    natural_width = logo.evaluate("img => img.naturalWidth")
    log_expected_actual("logo naturalWidth", "> 0", natural_width)
    assert natural_width > 0, "The brand logo downloaded but did not render."


# ==============================================================================
# Every service row is listed, in order, with a title and subtitle.
# ------------------------------------------------------------------------------
def test_landing_lists_every_service_row(
    page: Page, landing_base_url: str, ui_timeout_ms: int
):
    log_header("Landing page lists every service row")
    open_landing(page, landing_base_url, ui_timeout_ms)

    titles = [t.strip() for t in page.locator("a.row span.title").all_inner_texts()]
    expected = [row.title for row in SERVICE_ROWS]
    log_expected_actual("row titles, in order", expected, titles)
    assert titles == expected, f"Landing rows changed: {titles}"

    # Each row needs a subtitle and a chevron, or it reads as half-rendered.
    for row in SERVICE_ROWS:
        locator = row_locator(page, row.title)
        expect(locator).to_be_visible()
        subtitle = locator.locator("span.sub").inner_text().strip()
        assert subtitle, f"Row '{row.title}' has no subtitle."
        expect(locator.locator("span.chev")).to_have_text("›")


# ==============================================================================
# Each row points where it should. Marva is the odd one -- it links to its login
# page, not the app.
# ------------------------------------------------------------------------------
@pytest.mark.parametrize("row", SERVICE_ROWS, ids=lambda r: r.title)
def test_landing_row_targets_its_service(
    page: Page, landing_base_url: str, ui_timeout_ms: int, row
):
    log_header(f"Landing row targets its service: {row.title}")
    open_landing(page, landing_base_url, ui_timeout_ms)

    href = row_locator(page, row.title).get_attribute("href")
    log_expected_actual(f"'{row.title}' href", row.href, href)
    assert href == row.href, f"'{row.title}' links to {href}, not {row.href}."


# ==============================================================================
# No link on the front door is dead.
# ------------------------------------------------------------------------------
@pytest.mark.parametrize("row", SERVICE_ROWS, ids=lambda r: r.title)
def test_landing_row_link_resolves(
    page: Page, landing_base_url: str, ui_timeout_ms: int, row
):
    log_header(f"Landing row link resolves: {row.title}")
    open_landing(page, landing_base_url, ui_timeout_ms)

    response = page.request.get(f"{landing_base_url}{row.href}", timeout=30_000)
    log_expected_actual(f"GET {row.href}", "not 4xx/5xx", response.status)
    assert response.status < 400, (
        f"'{row.title}' links to {row.href}, which returned {response.status}."
    )


# ==============================================================================
# The footer links are there and work.
# ------------------------------------------------------------------------------
def test_landing_footer_links_resolve(
    page: Page, landing_base_url: str, ui_timeout_ms: int
):
    log_header("Landing footer links resolve")
    open_landing(page, landing_base_url, ui_timeout_ms)

    footer = page.locator("footer.links")
    expect(footer).to_be_visible()

    for label, href in FOOTER_LINKS:
        link = footer.get_by_role("link", name=label)
        expect(link).to_be_visible()
        assert link.get_attribute("href") == href, f"'{label}' points elsewhere."

        response = page.request.get(f"{landing_base_url}{href}", timeout=30_000)
        log_expected_actual(f"GET {href}", "not 4xx/5xx", response.status)
        assert response.status < 400, f"'{label}' ({href}) returned {response.status}."


# ==============================================================================
# Clicking a row actually gets you there -- worth more than checking hrefs.
# ------------------------------------------------------------------------------
def test_landing_search_row_navigates_to_the_search_view(
    page: Page, landing_base_url: str, ui_timeout_ms: int
):
    log_header("Landing 'Search' row navigates to the search view")
    open_landing(page, landing_base_url, ui_timeout_ms)

    row_locator(page, "Search").click()
    page.wait_for_load_state("domcontentloaded", timeout=ui_timeout_ms)

    log_expected_actual("path after click", "/api/search", urlparse(page.url).path)
    assert urlparse(page.url).path == "/api/search", f"Landed on {page.url}"
    expect(page.locator("h1.bc-doctype")).to_have_text("Search results")


# ==============================================================================
# The page loads with no browser errors. This page runs a script, so an error
# here means the status badge is silently dead.
# ------------------------------------------------------------------------------
def test_landing_loads_without_errors(
    page: Page, page_signals, landing_base_url: str, ui_timeout_ms: int
):
    log_header("Landing page loads without errors")
    open_landing(page, landing_base_url, ui_timeout_ms)
    page.wait_for_load_state("networkidle", timeout=ui_timeout_ms)

    log_expected_actual("page errors", [], page_signals.page_errors)
    log_expected_actual("server (5xx) responses", [], page_signals.server_errors)
    assert not page_signals.page_errors, page_signals.page_errors
    assert not page_signals.server_errors, page_signals.server_errors


# ==============================================================================
# The front door is usable on a phone.
# ------------------------------------------------------------------------------
def test_landing_does_not_scroll_sideways_on_mobile(
    page: Page, landing_base_url: str, ui_timeout_ms: int
):
    log_header("Landing page does not scroll sideways on mobile")
    page.set_viewport_size(MOBILE_VIEWPORT)
    open_landing(page, landing_base_url, ui_timeout_ms)

    scroll_width = page.evaluate("document.documentElement.scrollWidth")
    client_width = page.evaluate("document.documentElement.clientWidth")
    log_expected_actual("scrollWidth <= clientWidth", True, f"{scroll_width} <= {client_width}")
    assert scroll_width <= client_width + 1, (
        f"The page is {scroll_width}px wide in a {client_width}px viewport."
    )

    expect(row_locator(page, "Search")).to_be_visible()
