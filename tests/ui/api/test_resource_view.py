from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from tests.integration.support.logging import log_expected_actual, log_header
from tests.ui._support import full_stack_enabled
from tests.ui.api._support import field_labels, open_resource

# What a reader sees on a Hub, Work or Instance page. Ordering, sidebars and
# vocabulary labels each have their own file.
pytestmark = pytest.mark.skipif(
    not full_stack_enabled(),
    reason="API view tests require the full stack (Nginx + API)",
)

DOC_TYPES = {
    "works": "BIBFRAME Work",
    "instances": "BIBFRAME Instance",
    "hubs": "BIBFRAME Hub",
}


# ==============================================================================
# Each record type names itself and shows some fields.
# ------------------------------------------------------------------------------
@pytest.mark.parametrize("resource_type", ["works", "instances", "hubs"])
def test_resource_view_renders_its_document_type_and_fields(
    page: Page,
    api_base_url: str,
    resource_uuid_for,
    ui_timeout_ms: int,
    resource_type: str,
):
    log_header(f"API resource view renders document type and fields ({resource_type})")
    open_resource(
        page, api_base_url, resource_type, resource_uuid_for(resource_type), ui_timeout_ms
    )

    heading = page.locator("h1.bc-doctype")
    expect(heading).to_be_visible()
    log_expected_actual(
        "document type", DOC_TYPES[resource_type], heading.inner_text().strip()
    )
    expect(heading).to_contain_text(DOC_TYPES[resource_type])

    labels = field_labels(page)
    log_expected_actual("rendered field blocks", ">= 1", labels)
    assert labels, f"The {resource_type} view rendered no field blocks."


# ==============================================================================
# All four download formats are offered, and the Turtle link actually works.
# ------------------------------------------------------------------------------
def test_resource_view_alternative_formats_resolve(
    page: Page,
    api_base_url: str,
    seeded_resource_uuids: tuple[str, str],
    ui_timeout_ms: int,
):
    log_header("API resource view alternative formats resolve")
    _, instance_uuid = seeded_resource_uuids
    open_resource(page, api_base_url, "instances", instance_uuid, ui_timeout_ms)

    formats = page.locator("div.bc-formats")
    expect(formats).to_be_visible()
    labels = [text.strip() for text in formats.locator("a").all_inner_texts()]
    log_expected_actual("format links", "Turtle/RDF-XML/JSON-LD/N-Triples present", labels)
    for expected in ("Turtle", "RDF/XML", "JSON-LD", "N-Triples"):
        assert expected in labels, f"Missing '{expected}' in Alternative Formats: {labels}"

    turtle_href = formats.get_by_role("link", name="Turtle").get_attribute("href")
    assert turtle_href, "Turtle link has no href."
    response = page.request.get(turtle_href)
    log_expected_actual("Turtle link status", 200, response.status)
    assert response.status == 200, f"{turtle_href} returned {response.status}"


# ==============================================================================
# Marva can open an Instance but not a Work, so a Work shows the link disabled
# with a note explaining why.
# ------------------------------------------------------------------------------
def test_marva_link_is_offered_for_instances_and_explained_for_works(
    page: Page,
    api_base_url: str,
    seeded_resource_uuids: tuple[str, str],
    ui_timeout_ms: int,
):
    log_header("Marva link is offered for Instances, explained for Works")
    work_uuid, instance_uuid = seeded_resource_uuids

    open_resource(page, api_base_url, "instances", instance_uuid, ui_timeout_ms)
    instance_marva = page.locator("div.bc-formats").get_by_role("link", name="Marva")
    log_expected_actual("Instance offers a Marva link", ">= 1", instance_marva.count())
    assert instance_marva.count() >= 1, "An Instance should offer a live Marva link."

    open_resource(page, api_base_url, "works", work_uuid, ui_timeout_ms)
    formats = page.locator("div.bc-formats")
    disabled = formats.locator("span.bc-link-disabled")
    log_expected_actual("Work disables the Marva link", ">= 1", disabled.count())
    assert disabled.count() >= 1, (
        "A Work must not present a live Marva link; Marva loads Instances."
    )
    expect(formats.locator("span.bc-tooltip")).to_have_attribute(
        "role", "note"
    )


# ==============================================================================
# A stub record is flagged. Without it nothing tells the reader the record is
# still a placeholder.
# ------------------------------------------------------------------------------
def test_stub_record_is_flagged(
    page: Page, api_base_url: str, stub_record: tuple[str, str], ui_timeout_ms: int
):
    log_header("Stub record carries the stub flag")
    resource_type, uuid = stub_record
    open_resource(page, api_base_url, resource_type, uuid, ui_timeout_ms)

    flags = page.locator("span.bc-stub")
    log_expected_actual(f"stub flags on this {resource_type}", ">= 1", flags.count())
    assert flags.count() >= 1, f"The stub {resource_type} rendered no stub flag."

    # The flag is an icon, so it must carry its own accessible name and title.
    first = flags.first
    expect(first).to_have_attribute("role", "img")
    expect(first).to_have_attribute("aria-label", "Stub record")
    title = first.get_attribute("title")
    log_expected_actual("stub flag title", "explains the stub", title)
    assert title and "stub" in title.lower(), f"Stub flag title is unhelpful: {title!r}"


# ==============================================================================
# The stub flag sits in the heading, where a reader meets it first.
# ------------------------------------------------------------------------------
def test_stub_flag_marks_the_page_heading(
    page: Page, api_base_url: str, stub_record: tuple[str, str], ui_timeout_ms: int
):
    log_header("Stub flag marks the page heading")
    resource_type, uuid = stub_record
    open_resource(page, api_base_url, resource_type, uuid, ui_timeout_ms)

    heading_flag = page.locator("h1.bc-doctype span.bc-stub")
    log_expected_actual("stub flag in the h1", 1, heading_flag.count())
    assert heading_flag.count() == 1, (
        "A stub record should be flagged in its heading, not only further down."
    )
