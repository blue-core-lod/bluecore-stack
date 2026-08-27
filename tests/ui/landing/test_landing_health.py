from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

from tests.integration.support.logging import log_expected_actual, log_header
from tests.ui._support import full_stack_enabled
from tests.ui.landing._support import (
    CHECKING_LABEL,
    SERVICE_ROWS,
    open_landing,
    probe_is_reachable,
    row_locator,
)

# The live parts of the landing page: a status badge, and rows greyed out when
# their service is down.
#
# Both need a browser to run the script -- fetching / just returns markup with
# the badge still reading "Checking…".
pytestmark = pytest.mark.skipif(
    not full_stack_enabled(),
    reason="Landing page tests require the full stack (Nginx)",
)

# The checks fire once on load, so a short wait is plenty.
RESOLVE_TIMEOUT_MS = 15_000


def _settled_badge(page: Page):
    """The badge, once it has stopped saying "Checking…"."""
    badge = page.locator("#gw-badge")
    expect(badge.locator(".label")).not_to_have_text(
        CHECKING_LABEL, timeout=RESOLVE_TIMEOUT_MS
    )
    return badge


# ==============================================================================
# The badge updates without a reload, so a screen reader has to be told it
# changed.
# ------------------------------------------------------------------------------
def test_gateway_badge_is_an_accessible_live_region(
    page: Page, landing_base_url: str, ui_timeout_ms: int
):
    log_header("Gateway badge is an accessible live region")
    open_landing(page, landing_base_url, ui_timeout_ms)

    badge = page.locator("#gw-badge")
    expect(badge).to_be_visible()
    expect(badge).to_have_attribute("role", "status")
    expect(badge).to_have_attribute("aria-live", "polite")


# ==============================================================================
# The badge settles on one state. Stuck on "Checking…" means the script never
# ran.
# ------------------------------------------------------------------------------
def test_gateway_badge_resolves_out_of_its_placeholder(
    page: Page, landing_base_url: str, ui_timeout_ms: int
):
    log_header("Gateway badge resolves out of its placeholder")
    open_landing(page, landing_base_url, ui_timeout_ms)

    badge = _settled_badge(page)
    classes = badge.get_attribute("class") or ""
    label = badge.locator(".label").inner_text().strip()
    log_expected_actual("badge state", "one of ok/warn/down", f"{classes!r} -> {label!r}")

    states = [s for s in ("status-ok", "status-warn", "status-down") if s in classes]
    assert len(states) == 1, (
        f"The badge should carry exactly one state class, found {states} in {classes!r}."
    )
    assert label and label != CHECKING_LABEL, f"Badge label never updated: {label!r}"


# ==============================================================================
# The badge tells the truth: we ping the same two routes and check it agrees.
# ------------------------------------------------------------------------------
def test_gateway_badge_reports_the_real_state(
    page: Page, landing_base_url: str, ui_timeout_ms: int
):
    log_header("Gateway badge reports the real state")
    open_landing(page, landing_base_url, ui_timeout_ms)

    health_ok = page.request.get(f"{landing_base_url}/health-check", timeout=20_000).ok
    api_ok = page.request.get(f"{landing_base_url}/api/openapi.json", timeout=20_000).ok

    if health_ok and api_ok:
        expected_class, expected_label = "status-ok", "Gateway reachable (API OK)"
    elif health_ok:
        expected_class, expected_label = "status-warn", "Gateway OK, API unreachable"
    elif api_ok:
        expected_class, expected_label = "status-warn", "API OK, gateway unhealthy"
    else:
        expected_class, expected_label = "status-down", "Gateway unreachable"

    badge = _settled_badge(page)
    classes = badge.get_attribute("class") or ""
    label = badge.locator(".label").inner_text().strip()
    log_expected_actual(
        f"badge for health={health_ok} api={api_ok}",
        f"{expected_class} / {expected_label}",
        f"{classes} / {label}",
    )
    assert expected_class in classes, (
        f"/health-check ok={health_ok}, /api/openapi.json ok={api_ok}, so the badge "
        f"should be {expected_class}; it is {classes!r}."
    )
    assert label == expected_label, f"Badge label reads {label!r}."


# ==============================================================================
# Every row ends up marked up or down. One left unmarked means it was never
# checked.
# ------------------------------------------------------------------------------
def test_every_row_is_marked_once_probes_settle(
    page: Page, landing_base_url: str, ui_timeout_ms: int
):
    log_header("Every landing row is marked once probes settle")
    open_landing(page, landing_base_url, ui_timeout_ms)
    _settled_badge(page)

    for row in SERVICE_ROWS:
        locator = row_locator(page, row.title)
        expect(locator).to_have_attribute(
            "aria-disabled", re.compile(r"^(true|false)$"), timeout=RESOLVE_TIMEOUT_MS
        )


# ==============================================================================
# A row is greyed out only when its service really is down. Checked against a
# live ping, so it holds whatever is running.
# ------------------------------------------------------------------------------
@pytest.mark.parametrize("row", SERVICE_ROWS, ids=lambda r: r.title)
def test_row_availability_matches_its_probe(
    page: Page, landing_base_url: str, ui_timeout_ms: int, row
):
    log_header(f"Row availability matches its probe: {row.title}")
    open_landing(page, landing_base_url, ui_timeout_ms)
    _settled_badge(page)

    reachable = probe_is_reachable(page, row.probe, landing_base_url)
    locator = row_locator(page, row.title)
    expect(locator).to_have_attribute(
        "aria-disabled", "false" if reachable else "true", timeout=RESOLVE_TIMEOUT_MS
    )

    classes = locator.get_attribute("class") or ""
    log_expected_actual(
        f"'{row.title}' ({row.probe}) reachable={reachable}",
        "unavailable absent" if reachable else "unavailable present",
        classes,
    )
    if reachable:
        assert "unavailable" not in classes, (
            f"{row.probe} answers, but '{row.title}' is greyed out."
        )
    else:
        assert "unavailable" in classes, (
            f"{row.probe} is down, but '{row.title}' still reads as available."
        )


# ==============================================================================
# A row that is up still behaves as an ordinary link.
# ------------------------------------------------------------------------------
def test_available_rows_remain_clickable(
    page: Page, landing_base_url: str, ui_timeout_ms: int
):
    log_header("Available landing rows remain clickable")
    open_landing(page, landing_base_url, ui_timeout_ms)
    _settled_badge(page)

    available = [
        row
        for row in SERVICE_ROWS
        if (row_locator(page, row.title).get_attribute("aria-disabled")) == "false"
    ]
    log_expected_actual("rows marked available", ">= 1", [r.title for r in available])
    if not available:
        pytest.skip("No service in this stack is reachable, so nothing is clickable.")

    for row in available:
        locator = row_locator(page, row.title)
        expect(locator).to_be_enabled()
        assert locator.get_attribute("href"), f"'{row.title}' lost its href."
