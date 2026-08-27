from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from tests.integration.support.logging import log_expected_actual, log_header
from tests.ui._support import full_stack_enabled
from tests.ui.api._support import open_resource

# The sidebar each record type grows: an Instance links up to its Work, a Work
# lists its Instances, a Hub lists what it relates to. Worth checking here since
# render.py, which assembles them, has no unit tests of its own.
pytestmark = pytest.mark.skipif(
    not full_stack_enabled(),
    reason="API view tests require the full stack (Nginx + API)",
)

INSTANCE_ONLY_SECTIONS = {"Has Instance", "Instance of"}


def sidebar_headings(page: Page) -> list[str]:
    return [text.strip() for text in page.locator("aside.bc-sidebar h2").all_inner_texts()]


def sidebar_links_by_section(page: Page) -> dict[str, list[str]]:
    """Every sidebar section mapped to the hrefs it lists."""
    sidebar = page.locator("aside.bc-sidebar")
    if sidebar.count() == 0:
        return {}
    sections: dict[str, list[str]] = {}
    headings = sidebar_headings(page)
    lists = sidebar.locator("ul")
    for index, heading in enumerate(headings):
        if index >= lists.count():
            break
        links = lists.nth(index).locator("a")
        sections[heading] = [
            href
            for href in (links.nth(i).get_attribute("href") for i in range(links.count()))
            if href
        ]
    return sections


# ==============================================================================
# An Instance links back to its Work.
# ------------------------------------------------------------------------------
def test_instance_sidebar_links_to_its_work(
    page: Page,
    api_base_url: str,
    seeded_resource_uuids: tuple[str, str],
    ui_timeout_ms: int,
):
    log_header("Instance sidebar links to its Work")
    _, instance_uuid = seeded_resource_uuids
    open_resource(page, api_base_url, "instances", instance_uuid, ui_timeout_ms)

    sidebar = page.locator("aside.bc-sidebar")
    expect(sidebar).to_be_visible()
    headings = sidebar_headings(page)
    log_expected_actual("sidebar headings", ["Instance of"], headings)
    assert "Instance of" in headings, f"Instance sidebar headings: {headings}"

    work_links = sidebar.locator("a[href*='/works/']")
    log_expected_actual("links to a Work", ">= 1", work_links.count())
    assert work_links.count() >= 1, "The 'Instance of' section links to no Work."


# ==============================================================================
# A Work lists the Instances beneath it.
# ------------------------------------------------------------------------------
def test_work_sidebar_lists_its_instances(
    page: Page,
    api_base_url: str,
    seeded_resource_uuids: tuple[str, str],
    ui_timeout_ms: int,
):
    log_header("Work sidebar lists its Instances")
    work_uuid, _ = seeded_resource_uuids
    open_resource(page, api_base_url, "works", work_uuid, ui_timeout_ms)

    sidebar = page.locator("aside.bc-sidebar")
    expect(sidebar).to_be_visible()
    headings = sidebar_headings(page)
    log_expected_actual("sidebar headings", ["Has Instance"], headings)
    assert "Has Instance" in headings, f"Work sidebar headings: {headings}"

    instance_links = sidebar.locator("a[href*='/instances/']")
    log_expected_actual("links to an Instance", ">= 1", instance_links.count())
    assert instance_links.count() >= 1, "The 'Has Instance' section links to no Instance."


# ==============================================================================
# A heading never appears twice; repeats fold into the section already open.
# ------------------------------------------------------------------------------
@pytest.mark.parametrize("resource_type", ["works", "instances"])
def test_sidebar_headings_are_not_repeated(
    page: Page,
    api_base_url: str,
    resource_uuid_for,
    ui_timeout_ms: int,
    resource_type: str,
):
    log_header(f"Sidebar headings are not repeated ({resource_type})")
    open_resource(
        page, api_base_url, resource_type, resource_uuid_for(resource_type), ui_timeout_ms
    )

    headings = sidebar_headings(page)
    if not headings:
        pytest.skip(f"This {resource_type} record has no sidebar.")

    duplicates = [h for h in set(headings) if headings.count(h) > 1]
    log_expected_actual("repeated headings", [], duplicates)
    assert not duplicates, (
        f"These sections should have folded into one heading each: {duplicates}"
    )


# ==============================================================================
# Every section lists something; an empty heading is just noise.
# ------------------------------------------------------------------------------
@pytest.mark.parametrize("resource_type", ["works", "instances"])
def test_sidebar_sections_are_not_empty(
    page: Page,
    api_base_url: str,
    resource_uuid_for,
    ui_timeout_ms: int,
    resource_type: str,
):
    log_header(f"Sidebar sections list something ({resource_type})")
    open_resource(
        page, api_base_url, resource_type, resource_uuid_for(resource_type), ui_timeout_ms
    )

    sections = sidebar_links_by_section(page)
    if not sections:
        pytest.skip(f"This {resource_type} record has no sidebar.")

    sidebar = page.locator("aside.bc-sidebar")
    for index, heading in enumerate(sidebar_headings(page)):
        entries = sidebar.locator("ul").nth(index).locator("li").count()
        log_expected_actual(f"'{heading}' entries", ">= 1", entries)
        assert entries >= 1, f"Sidebar section '{heading}' rendered with no entries."


# ==============================================================================
# A Hub's sidebar never shows Instance sections; those belong to Works.
# ------------------------------------------------------------------------------
def test_hub_sidebar_carries_only_hub_sections(
    page: Page, api_base_url: str, hub_uuid_with_sidebar: str, ui_timeout_ms: int
):
    log_header("Hub sidebar carries only Hub sections")
    open_resource(page, api_base_url, "hubs", hub_uuid_with_sidebar, ui_timeout_ms)

    expect(page.locator("aside.bc-sidebar")).to_be_visible()
    headings = sidebar_headings(page)
    log_expected_actual("hub sidebar headings", "Hub sections only", headings)
    assert headings, "Hub sidebar rendered with no sections."

    forbidden = [h for h in headings if h in INSTANCE_ONLY_SECTIONS]
    assert not forbidden, f"A Hub sidebar must not carry Instance sections: {forbidden}"


# ==============================================================================
# NOT a rule: one Work may appear under two headings, since "Has Expression" and
# "Series of" say different things about it. Only Associated Works is deduped.
# ------------------------------------------------------------------------------


