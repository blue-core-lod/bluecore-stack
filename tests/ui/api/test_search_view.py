from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest
from playwright.sync_api import Page, expect

from tests.integration.support.logging import log_expected_actual, log_header
from tests.integration.support.sample_data import SAMPLE_SEARCH_QUERY
from tests.ui._support import full_stack_enabled
from tests.ui.api._support import open_search, result_count, result_hrefs

# The HTML search page -- mind the trailing slash, /search/ returns JSON and
# /search returns the page. Scoping and the mobile layout have their own files.
pytestmark = pytest.mark.skipif(
    not full_stack_enabled(),
    reason="API view tests require the full stack (Nginx + API)",
)


# ==============================================================================
# The page renders with its title and heading.
# ------------------------------------------------------------------------------
def test_search_view_renders_page_shell(page: Page, api_base_url: str, ui_timeout_ms: int):
    log_header("API search view renders page shell")
    open_search(page, api_base_url, ui_timeout_ms)

    log_expected_actual("page title", "'Search results · Blue Core'", page.title())
    expect(page).to_have_title("Search results · Blue Core")
    expect(page.locator("h1.bc-doctype")).to_have_text("Search results")


# ==============================================================================
# The search form offers all its type and scope options.
# ------------------------------------------------------------------------------
def test_search_form_controls_are_present(page: Page, api_base_url: str, ui_timeout_ms: int):
    log_header("API search view exposes its form controls")
    open_search(page, api_base_url, ui_timeout_ms)

    type_select = page.get_by_label("Resource type")
    scope_select = page.get_by_label("Search scope")
    expect(type_select).to_be_visible()
    expect(scope_select).to_be_visible()

    type_options = [t.strip() for t in type_select.locator("option").all_inner_texts()]
    scope_options = [t.strip() for t in scope_select.locator("option").all_inner_texts()]
    log_expected_actual("resource type options", "All/Works/Instances/Hubs", type_options)
    log_expected_actual("scope options", "All fields/Title", scope_options)
    assert type_options == [
        "BIBFRAME All",
        "BIBFRAME Works",
        "BIBFRAME Instances",
        "BIBFRAME Hubs",
    ]
    assert scope_options == ["All fields", "Title"]

    expect(page.locator("input[type='search'][name='q']")).to_be_visible()
    # Present, but not asserted visible: the submit button is clipped to 1px on
    # desktop and only becomes a real control below the 760px breakpoint.
    # test_search_responsive.py covers that.
    expect(page.get_by_role("button", name="Search")).to_have_count(1)


# ==============================================================================
# Submitting the form runs the search and echoes the query back.
# ------------------------------------------------------------------------------
def test_search_form_submits_query_to_html_view(
    page: Page, api_base_url: str, ui_timeout_ms: int
):
    log_header("API search form submits to the HTML search route")
    open_search(page, api_base_url, ui_timeout_ms)

    search_input = page.locator("input[type='search'][name='q']")
    search_input.fill(SAMPLE_SEARCH_QUERY)
    # Submit with Enter, not by clicking the button: bluecore.css clips the
    # submit button to 1px on desktop, so Enter is the real desktop interaction.
    search_input.press("Enter")
    page.wait_for_load_state("domcontentloaded", timeout=ui_timeout_ms)

    parsed = urlparse(page.url)
    log_expected_actual("submitted path", "ends with /search", parsed.path)
    log_expected_actual("q parameter", SAMPLE_SEARCH_QUERY, parse_qs(parsed.query).get("q"))
    assert parsed.path.endswith("/search"), f"Form submitted to {page.url}"
    assert parse_qs(parsed.query).get("q") == [SAMPLE_SEARCH_QUERY]

    expect(page.locator("p.bc-result-num")).to_contain_text(SAMPLE_SEARCH_QUERY)
    expect(page.locator("h1.bc-doctype")).to_have_text("Search results")


# ==============================================================================
# Filtering by type shows only that type's group.
# ------------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("search_type", "expected_heading"),
    [("works", "Works"), ("instances", "Instances"), ("hubs", "Hubs")],
)
def test_search_view_type_filter_shows_only_its_group(
    page: Page,
    api_base_url: str,
    ui_timeout_ms: int,
    search_type: str,
    expected_heading: str,
):
    log_header(f"API search view type filter: {search_type}")
    open_search(page, api_base_url, ui_timeout_ms, type=search_type, limit=5, offset=0)

    headings = [t.strip() for t in page.locator("h2.bc-results-heading").all_inner_texts()]
    log_expected_actual(f"group headings for type={search_type}", [expected_heading], headings)
    if not headings:
        pytest.skip(f"No {search_type} seeded in this stack.")
    assert headings == [expected_heading], (
        f"A type={search_type} search should show only the '{expected_heading}' group."
    )


# ==============================================================================
# An "all" search groups results as Works, then Instances, then Hubs.
# ------------------------------------------------------------------------------
def test_search_view_all_groups_in_declared_order(
    page: Page, api_base_url: str, ui_timeout_ms: int
):
    log_header("API search view groups an 'all' search in declared order")
    open_search(page, api_base_url, ui_timeout_ms, type="all", limit=100, offset=0)

    headings = [t.strip() for t in page.locator("h2.bc-results-heading").all_inner_texts()]
    log_expected_actual("group headings", "subset of Works/Instances/Hubs, in order", headings)
    assert headings, "An 'all' search over a seeded stack rendered no groups."
    assert set(headings) <= {"Works", "Instances", "Hubs"}, headings

    declared = ["Works", "Instances", "Hubs"]
    assert headings == [h for h in declared if h in headings], (
        f"Groups are out of declared order: {headings}"
    )


# ==============================================================================
# The form remembers the type and scope you chose, so paging or reloading keeps
# the search you asked for.
# ------------------------------------------------------------------------------
@pytest.mark.parametrize("search_type", ["all", "works", "instances", "hubs"])
@pytest.mark.parametrize("search_scope", ["all", "title"])
def test_search_form_reflects_active_type_and_scope(
    page: Page,
    api_base_url: str,
    ui_timeout_ms: int,
    search_type: str,
    search_scope: str,
):
    log_header(f"API search form reflects type={search_type} scope={search_scope}")
    open_search(
        page,
        api_base_url,
        ui_timeout_ms,
        query=SAMPLE_SEARCH_QUERY,
        type=search_type,
        scope=search_scope,
    )

    selected_type = page.get_by_label("Resource type").input_value()
    selected_scope = page.get_by_label("Search scope").input_value()
    log_expected_actual("selected type", search_type, selected_type)
    log_expected_actual("selected scope", search_scope, selected_scope)
    assert selected_type == search_type, (
        f"Type select shows '{selected_type}', not the requested '{search_type}'."
    )
    assert selected_scope == search_scope, (
        f"Scope select shows '{selected_scope}', not the requested '{search_scope}'."
    )

    # The query itself must survive the round trip too, or paging loses it.
    assert page.locator("input[type='search'][name='q']").input_value() == SAMPLE_SEARCH_QUERY


# ==============================================================================
# Every result links to a record page and has visible text.
# ------------------------------------------------------------------------------
def test_search_result_links_target_resource_views(
    page: Page, api_base_url: str, ui_timeout_ms: int
):
    log_header("API search results link to resource views")
    open_search(page, api_base_url, ui_timeout_ms, type="all", limit=5, offset=0)

    hrefs = result_hrefs(page)
    if not hrefs:
        pytest.skip("No seeded results to link to.")

    log_expected_actual("result hrefs", "works/instances/hubs URIs", hrefs[:5])
    for href in hrefs[:5]:
        assert any(part in href for part in ("/works/", "/instances/", "/hubs/")), (
            f"Result link does not target a resource view: {href}"
        )

    links = page.locator("ul.bc-results li a")
    for index in range(min(links.count(), 5)):
        assert links.nth(index).inner_text().strip(), "A result rendered with an empty title."


# ==============================================================================
# Next moves to the following page and carries the rest of the search with it.
# ------------------------------------------------------------------------------
def test_search_view_pagination_advances(page: Page, api_base_url: str, ui_timeout_ms: int):
    log_header("API search view pagination advances")
    open_search(
        page, api_base_url, ui_timeout_ms,
        query=SAMPLE_SEARCH_QUERY, type="all", limit=1, offset=0,
    )

    next_link = page.get_by_role("link", name="Next")
    if next_link.count() == 0:
        pytest.skip("Fewer than two matching resources; no pager to exercise.")

    expect(page.locator("nav.bc-pager").first).to_be_visible()
    expect(page.locator("span.bc-pager-status").first).to_contain_text("of")

    next_link.first.click()
    page.wait_for_load_state("domcontentloaded", timeout=ui_timeout_ms)

    params = parse_qs(urlparse(page.url).query)
    log_expected_actual("offset after Next", ["1"], params.get("offset"))
    assert params.get("offset") == ["1"], f"Next did not advance the offset: {page.url}"
    # The rest of the search must ride along, or page two silently widens it.
    assert params.get("q") == [SAMPLE_SEARCH_QUERY], f"Next dropped the query: {page.url}"
    assert params.get("limit") == ["1"], f"Next dropped the page size: {page.url}"
    expect(page.get_by_role("link", name="Previous").first).to_be_visible()


# ==============================================================================
# A search with no matches says "No results." and offers no pager.
# ------------------------------------------------------------------------------
def test_search_view_empty_state(page: Page, api_base_url: str, ui_timeout_ms: int):
    log_header("API search view renders its empty state")
    open_search(
        page, api_base_url, ui_timeout_ms,
        query="zzzznosuchresourceexistszzzz", type="all",
    )

    total = result_count(page)
    log_expected_actual("result total", 0, total)
    assert total == 0, f"Expected no matches, got {total}."

    expect(page.locator("p.bc-muted", has_text="No results.")).to_be_visible()
    expect(page.locator("h2.bc-results-heading")).to_have_count(0)
    expect(page.locator("ul.bc-results")).to_have_count(0)
    expect(page.locator("nav.bc-pager")).to_have_count(0)
