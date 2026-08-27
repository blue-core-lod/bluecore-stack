from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page

from tests.integration.support.logging import log_expected_actual, log_header
from tests.ui._support import full_stack_enabled
from tests.ui.api._support import field_labels, field_values, open_resource

# Records store things like language as bare URIs, and the page is meant to show
# the label instead -- "French", not ".../languages/fre".
#
# The resolver itself is unit-tested upstream; these check it reaches the page.
pytestmark = pytest.mark.skipif(
    not full_stack_enabled(),
    reason="API view tests require the full stack (Nginx + API)",
)

# Fields whose values are stored as URIs but should read as words.
VOCABULARY_BACKED_LABELS = (
    "Type",
    "Language",
    "Content",
    "Genre Form",
    "Media",
    "Issuance",
    "Carrier",
)

_URI = re.compile(r"^https?://", re.IGNORECASE)

# Fields where a URL is the right answer, because the value IS an address.
URI_BEARING_LABELS = {"Electronic locator", "Electronic Locator", "Item Portion"}


def _uri_valued(values: list[str]) -> list[str]:
    return [value for value in values if _URI.match(value.strip())]


# ==============================================================================
# Vocabulary fields show words, not the URIs they were stored as.
# ------------------------------------------------------------------------------
@pytest.mark.parametrize("resource_type", ["works", "instances", "hubs"])
def test_vocabulary_fields_show_labels_not_uris(
    page: Page,
    api_base_url: str,
    resource_uuid_for,
    ui_timeout_ms: int,
    resource_type: str,
):
    log_header(f"Vocabulary fields show labels, not URIs ({resource_type})")
    open_resource(
        page, api_base_url, resource_type, resource_uuid_for(resource_type), ui_timeout_ms
    )

    rendered = field_labels(page)
    checked: dict[str, list[str]] = {}
    for label in VOCABULARY_BACKED_LABELS:
        if label not in rendered:
            continue
        values = field_values(page, label)
        if values:
            checked[label] = values

    if not checked:
        pytest.skip(f"This {resource_type} record carries no vocabulary-backed field.")

    unresolved = {
        label: _uri_valued(values)
        for label, values in checked.items()
        if _uri_valued(values)
    }
    log_expected_actual("fields still showing a bare URI", {}, unresolved)
    assert not unresolved, (
        "These vocabulary values reached the page as raw URIs instead of "
        f"resolved labels: {unresolved}"
    )


# ==============================================================================
# No field shows a bare URI where a reader expects words.
# ------------------------------------------------------------------------------
@pytest.mark.parametrize("resource_type", ["works", "instances", "hubs"])
def test_no_field_renders_a_bare_uri_as_its_text(
    page: Page,
    api_base_url: str,
    resource_uuid_for,
    ui_timeout_ms: int,
    resource_type: str,
):
    log_header(f"No field renders a bare URI as its text ({resource_type})")
    open_resource(
        page, api_base_url, resource_type, resource_uuid_for(resource_type), ui_timeout_ms
    )

    offenders: dict[str, list[str]] = {}
    for label in field_labels(page):
        if label in URI_BEARING_LABELS:
            continue
        bare = _uri_valued(field_values(page, label))
        if bare:
            offenders[label] = bare

    log_expected_actual("fields showing a bare URI", {}, offenders)
    assert not offenders, (
        f"These fields show a URI where a reader expects words: {offenders}"
    )


# ==============================================================================
# Links have readable text rather than showing their own address.
# ------------------------------------------------------------------------------
@pytest.mark.parametrize("resource_type", ["works", "instances", "hubs"])
def test_linked_values_have_readable_link_text(
    page: Page,
    api_base_url: str,
    resource_uuid_for,
    ui_timeout_ms: int,
    resource_type: str,
):
    log_header(f"Linked values have readable link text ({resource_type})")
    open_resource(
        page, api_base_url, resource_type, resource_uuid_for(resource_type), ui_timeout_ms
    )

    links = page.locator("div.bc-field:not(.bc-formats) a")
    if links.count() == 0:
        pytest.skip(f"This {resource_type} record renders no linked values.")

    unreadable: list[str] = []
    for index in range(links.count()):
        link = links.nth(index)
        text = (link.inner_text() or "").strip()
        href = link.get_attribute("href") or ""
        if not text:
            unreadable.append(f"empty text for {href}")
        elif _URI.match(text) and text == href:
            unreadable.append(f"link labelled with its own href: {href}")

    log_expected_actual("links without readable text", [], unreadable)
    assert not unreadable, (
        f"These links reached the page without a resolved label: {unreadable}"
    )
