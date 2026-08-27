from __future__ import annotations

import pytest
from playwright.sync_api import Page

from tests.integration.support.logging import log_expected_actual, log_header
from tests.ui._support import full_stack_enabled
from tests.ui.api._support import field_labels, open_resource

# The download/editor block at the foot of the page.
FORMATS_HEADINGS = ["Alternative Formats", "Blue Core Editors"]

# Where things sit on a rendered record page. The full field order is covered by
# bluecore_api's unit tests; these check what you can only see once it is drawn.
pytestmark = pytest.mark.skipif(
    not full_stack_enabled(),
    reason="API view tests require the full stack (Nginx + API)",
)


# ==============================================================================
# Type sits directly after the titles.
# ------------------------------------------------------------------------------
@pytest.mark.parametrize("resource_type", ["works", "hubs"])
def test_type_field_follows_the_titles(
    page: Page,
    api_base_url: str,
    resource_uuid_for,
    ui_timeout_ms: int,
    resource_type: str,
):
    log_header(f"Resource view places Type after the titles ({resource_type})")
    open_resource(
        page, api_base_url, resource_type, resource_uuid_for(resource_type), ui_timeout_ms
    )

    rendered = field_labels(page)
    if "Type" not in rendered:
        pytest.skip(f"This {resource_type} record adds no type beyond the implied one.")

    titles = ("Title", "Other Titles (e.g. Variant)")
    title_positions = [i for i, label in enumerate(rendered) if label in titles]
    type_position = rendered.index("Type")
    log_expected_actual(
        "Type index", (max(title_positions) + 1) if title_positions else 0, type_position
    )
    if title_positions:
        assert type_position == max(title_positions) + 1, (
            f"Type should follow the last title. Rendered: {rendered}"
        )
    else:
        assert type_position == 0, f"With no title, Type should lead. Rendered: {rendered}"


# ==============================================================================
# Admin Metadata sinks below every other field.
# ------------------------------------------------------------------------------
@pytest.mark.parametrize("resource_type", ["works", "instances", "hubs"])
def test_admin_metadata_renders_last(
    page: Page,
    api_base_url: str,
    resource_uuid_for,
    ui_timeout_ms: int,
    resource_type: str,
):
    log_header(f"Resource view places Admin Metadata last ({resource_type})")
    open_resource(
        page, api_base_url, resource_type, resource_uuid_for(resource_type), ui_timeout_ms
    )

    rendered = field_labels(page)
    if "Admin Metadata" not in rendered:
        pytest.skip(f"This {resource_type} record carries no Admin Metadata.")

    trailing = rendered[rendered.index("Admin Metadata"):]
    log_expected_actual("labels from first Admin Metadata on", "all Admin Metadata", trailing)
    assert set(trailing) == {"Admin Metadata"}, (
        f"Fields render after Admin Metadata: {trailing}"
    )


# ==============================================================================
# Only fields holding more than one value get bullets, and Admin Metadata never
# does.
# ------------------------------------------------------------------------------
@pytest.mark.parametrize("resource_type", ["works", "instances"])
def test_bullets_mark_only_multi_value_fields(
    page: Page,
    api_base_url: str,
    resource_uuid_for,
    ui_timeout_ms: int,
    resource_type: str,
):
    log_header(f"Bullets mark only multi-value fields ({resource_type})")
    open_resource(
        page, api_base_url, resource_type, resource_uuid_for(resource_type), ui_timeout_ms
    )

    bulleted = page.locator("div.bc-field:has(ul.bc-bulleted)")
    for index in range(bulleted.count()):
        field = bulleted.nth(index)
        label = field.locator("h2").inner_text().strip()
        values = field.locator("ul.bc-bulleted li.bc-list-value").count()
        log_expected_actual(f"'{label}' bulleted values", ">= 2", values)
        assert values >= 2, f"'{label}' is bulleted but holds {values} value(s)."
        assert label != "Admin Metadata", "Admin Metadata must never bullet."

    plain = page.locator("div.bc-field p.bc-value")
    log_expected_actual("plain single-value fields", ">= 1", plain.count())
    assert plain.count() >= 1, "No field rendered a plain single value."


# ==============================================================================
# The download/editor block sits below everything else on the page.
# ------------------------------------------------------------------------------
@pytest.mark.parametrize("resource_type", ["works", "instances", "hubs"])
def test_formats_block_renders_below_the_fields(
    page: Page,
    api_base_url: str,
    resource_uuid_for,
    ui_timeout_ms: int,
    resource_type: str,
):
    log_header(f"Formats block renders last ({resource_type})")
    open_resource(
        page, api_base_url, resource_type, resource_uuid_for(resource_type), ui_timeout_ms
    )

    all_headings = [t.strip() for t in page.locator("div.bc-field h2").all_inner_texts()]
    log_expected_actual("last two headings", FORMATS_HEADINGS, all_headings[-2:])
    assert all_headings[-2:] == FORMATS_HEADINGS, (
        f"The formats block is not the final section: {all_headings}"
    )
