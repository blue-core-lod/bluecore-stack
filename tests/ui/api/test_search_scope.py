from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page

from tests.integration.support.logging import log_expected_actual, log_header
from tests.integration.support.sample_data import SAMPLE_SEARCH_QUERY
from tests.ui._support import full_stack_enabled
from tests.ui.api._support import (
    field_values,
    open_resource,
    open_search,
    result_count,
    result_hrefs,
)

# Search scoping as a reader meets it, through Nginx on the deployed stack.
#
# That "title" really matches only titles is bluecore_api's
# test_title_scope_excludes_non_title_values; checking it here meant seeding a
# record first, for no extra coverage.
pytestmark = pytest.mark.skipif(
    not full_stack_enabled(),
    reason="API view tests require the full stack (Nginx + API)",
)

# Four letters or more, so a search term is distinctive enough to be useful.
_TOKEN = re.compile(r"[A-Za-z]{4,}")


def _distinctive_terms(values: list[str], exclude: str) -> list[str]:
    """Word-like tokens from `values` that do not appear in `exclude`."""
    excluded = exclude.lower()
    terms: list[str] = []
    for value in values:
        for token in _TOKEN.findall(value):
            lowered = token.lower()
            if lowered not in excluded and lowered not in terms:
                terms.append(lowered)
    return terms


# ==============================================================================
# A word from a record's own title finds that record when scoped to titles.
# ------------------------------------------------------------------------------
def test_title_scope_finds_a_record_by_its_own_title(
    page: Page,
    api_base_url: str,
    seeded_resource_uuids: tuple[str, str],
    ui_timeout_ms: int,
):
    log_header("Title scope finds a record by its own title")
    work_uuid, _ = seeded_resource_uuids
    open_resource(page, api_base_url, "works", work_uuid, ui_timeout_ms)

    titles = field_values(page, "Title")
    if not titles:
        pytest.skip("Seeded Work renders no Title field to search on.")

    terms = _distinctive_terms(titles, exclude="")
    if not terms:
        pytest.skip(f"No searchable token in the title {titles!r}.")
    term = terms[0]

    open_search(page, api_base_url, ui_timeout_ms, query=term, type="works", scope="title")
    hrefs = result_hrefs(page)
    log_expected_actual(f"title search '{term}' finds the record", True, work_uuid in " ".join(hrefs))
    assert any(work_uuid in href for href in hrefs), (
        f"A title-scoped search for '{term}', taken from this record's own title, "
        f"did not return it. Results: {hrefs[:5]}"
    )


# ==============================================================================
# Scoping to titles can only ever narrow a search, never widen it.
# ------------------------------------------------------------------------------
def test_title_scope_is_a_subset_of_all_fields(
    page: Page, api_base_url: str, ui_timeout_ms: int
):
    log_header("Title scope never widens the result set")

    def total_for(scope: str) -> int:
        open_search(
            page, api_base_url, ui_timeout_ms,
            query=SAMPLE_SEARCH_QUERY, type="all", scope=scope,
        )
        return result_count(page)

    all_fields_total = total_for("all")
    title_total = total_for("title")
    log_expected_actual(
        "title total <= all-fields total", True, f"{title_total} <= {all_fields_total}"
    )
    assert title_total <= all_fields_total, (
        f"Title scope returned more ({title_total}) than all fields ({all_fields_total})."
    )
