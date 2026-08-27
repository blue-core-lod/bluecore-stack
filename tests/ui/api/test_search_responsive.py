from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest
from playwright.sync_api import Page, expect

from tests.integration.support.logging import log_expected_actual, log_header
from tests.integration.support.sample_data import SAMPLE_SEARCH_QUERY
from tests.ui._support import full_stack_enabled
from tests.ui.api._support import open_search

# The search form changes shape at 760px: on desktop the submit button is hidden
# and you press Enter, on mobile it becomes a real button behind the hamburger.
# The markup is identical either side, so only a browser can tell them apart.

DESKTOP_VIEWPORT = {"width": 1280, "height": 720}
MOBILE_VIEWPORT = {"width": 420, "height": 860}

pytestmark = pytest.mark.skipif(
    not full_stack_enabled(),
    reason="API view tests require the full stack (Nginx + API)",
)


def _button_box(page: Page):
    return page.get_by_role("button", name="Search").bounding_box()


# ==============================================================================
# On desktop the submit button is hidden from sight but still there for screen
# readers.
# ------------------------------------------------------------------------------
def test_submit_button_is_screen_reader_only_on_desktop(
    page: Page, api_base_url: str, ui_timeout_ms: int
):
    log_header("Search submit button is screen-reader-only on desktop")
    page.set_viewport_size(DESKTOP_VIEWPORT)
    open_search(page, api_base_url, ui_timeout_ms)

    expect(page.get_by_role("button", name="Search")).to_have_count(1)
    box = _button_box(page)
    log_expected_actual("desktop button size", "clipped to ~1px", box)
    assert box is not None, "Submit button has no box at all."
    assert box["width"] <= 2 and box["height"] <= 2, (
        f"Submit button is {box['width']}x{box['height']} on desktop; it should be "
        "clipped to 1px, with Enter as the visible interaction."
    )


# ==============================================================================
# On mobile it becomes a real button, and clicking it runs the search.
# ------------------------------------------------------------------------------
def test_submit_button_becomes_a_real_control_on_mobile(
    page: Page, api_base_url: str, ui_timeout_ms: int
):
    log_header("Search submit button is a real control on mobile")
    page.set_viewport_size(MOBILE_VIEWPORT)
    open_search(page, api_base_url, ui_timeout_ms)

    # The form lives behind the pure-CSS hamburger at this width; open it.
    page.locator("label.bc-hamburger").click()

    button = page.get_by_role("button", name="Search")
    expect(button).to_be_visible()
    box = _button_box(page)
    log_expected_actual("mobile button size", "a full-width control", box)
    assert box is not None and box["height"] >= 20 and box["width"] >= 100, (
        f"Submit button is {box} on mobile; it should be a real control."
    )

    page.locator("input[type='search'][name='q']").fill(SAMPLE_SEARCH_QUERY)
    button.click()
    page.wait_for_load_state("domcontentloaded", timeout=ui_timeout_ms)

    params = parse_qs(urlparse(page.url).query)
    log_expected_actual("q after mobile submit", [SAMPLE_SEARCH_QUERY], params.get("q"))
    assert params.get("q") == [SAMPLE_SEARCH_QUERY], (
        f"Clicking the mobile submit button did not run the search: {page.url}"
    )


# ==============================================================================
# The hamburger shows on mobile only.
# ------------------------------------------------------------------------------
def test_hamburger_is_mobile_only(page: Page, api_base_url: str, ui_timeout_ms: int):
    log_header("Hamburger toggle appears only below the breakpoint")

    page.set_viewport_size(DESKTOP_VIEWPORT)
    open_search(page, api_base_url, ui_timeout_ms)
    desktop_box = page.locator("label.bc-hamburger").bounding_box()
    log_expected_actual("hamburger on desktop", "hidden", desktop_box)
    assert desktop_box is None or desktop_box["width"] == 0, (
        f"The hamburger should be hidden on desktop, but rendered {desktop_box}."
    )

    page.set_viewport_size(MOBILE_VIEWPORT)
    open_search(page, api_base_url, ui_timeout_ms)
    expect(page.locator("label.bc-hamburger")).to_be_visible()


# ==============================================================================
# The page does not scroll sideways on a phone.
# ------------------------------------------------------------------------------
def test_mobile_layout_does_not_scroll_sideways(
    page: Page, api_base_url: str, ui_timeout_ms: int
):
    log_header("Mobile search view does not scroll sideways")
    page.set_viewport_size(MOBILE_VIEWPORT)
    open_search(page, api_base_url, ui_timeout_ms, query=SAMPLE_SEARCH_QUERY)

    scroll_width = page.evaluate("document.documentElement.scrollWidth")
    client_width = page.evaluate("document.documentElement.clientWidth")
    log_expected_actual("scrollWidth <= clientWidth", True, f"{scroll_width} <= {client_width}")
    assert scroll_width <= client_width + 1, (
        f"The page is {scroll_width}px wide in a {client_width}px viewport, "
        "so it scrolls horizontally on a phone."
    )
