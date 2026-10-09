from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest
from playwright.sync_api import Page, expect
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from tests.integration.support.logging import log_expected_actual, log_header
from tests.ui._support import (
    KEYCLOAK_AUTH_PATH,
    full_stack_enabled,
    keycloak_password,
    keycloak_username,
    marva_url,
)

# Real-browser tests for the Marva editor. They drive Chromium (via the
# pytest-playwright `page` fixture) through Nginx, so they need the full stack.
# The runner enables it by default (INTEGRATION_FULL_STACK=1); skip cleanly when
# a lightweight run omits Nginx/Marva.
# tests/integration/marva covers the middleware's HTTP contract in every mode.
#
# ==============================================================================
# How login works here (and why it runs in every mode)
# ------------------------------------------------------------------------------
# Unlike Sinopia, Marva's URLs are relative and its post-login redirect comes
# from the middleware's MARVA_REDIRECT_BASE (http://localhost/marva/ locally),
# not from the bundle. So the SSO round trip stays on the local stack with the
# published image too, and the authenticated tests run in both modes.
#
# Tests that depend on newer Marva features (the logged-out redirect before the
# app mounts, the Blue Core "Export to Catalog" menu item) SKIP when the Marva
# build under test predates them, e.g. an older published `:latest` image.
# Build Marva from a branch to run them: --marva-ref <branch> or --dev-mode.
# ------------------------------------------------------------------------------
pytestmark = pytest.mark.skipif(
    not full_stack_enabled(),
    reason="Marva UI tests require the full stack (Nginx + Marva)",
)

MIDDLEWARE_CALLBACK_PATH = "/marva/util/auth/callback"


def _open_login(page: Page, timeout: int) -> None:
    """Start the SSO login the same way Marva's own login does (via the middleware)."""
    page.goto(f"{marva_url()}/util/auth/login", wait_until="domcontentloaded", timeout=timeout)
    page.wait_for_url(f"**{KEYCLOAK_AUTH_PATH}**", timeout=timeout)


def _dismiss_cataloging_code(page: Page) -> None:
    """
    A new browser has no cataloging code saved, so Marva opens its Account modal
    and blocks the page until one is entered. Fill it in when it appears.
    """
    code = page.get_by_placeholder("Cataloging Code")
    try:
        code.wait_for(state="visible", timeout=5_000)
    except PlaywrightTimeoutError:
        return
    code.fill("uitest")
    page.get_by_role("button", name="Done").click()
    expect(code).to_be_hidden()


def _login(page: Page, timeout: int) -> None:
    """Log into Marva through Keycloak and land back on the local home page."""
    _open_login(page, timeout)
    page.locator("#username").fill(keycloak_username())
    page.locator("#password").fill(keycloak_password())
    page.locator("#kc-login").click()
    page.wait_for_url(f"{marva_url()}/**", timeout=timeout)
    _dismiss_cataloging_code(page)


def _open_blank_monograph(page: Page, timeout: int) -> None:
    """From the home page, open a new blank Monograph record in the editor."""
    page.get_by_text("Click Here").first.click()
    # The blank-template buttons are the last set on the page (after "Load with profile").
    page.locator("button", has_text="Monograph").last.click()
    page.wait_for_url("**/marva/edit/**", timeout=timeout)


@pytest.fixture
def authenticated_page(page: Page, ui_timeout_ms: int) -> Page:
    """A page logged into Marva, sitting on the home page."""
    _login(page, ui_timeout_ms)
    return page


# ========================================================================
# A logged-out visit sends the browser straight to the Keycloak login, with
# the OAuth parameters the middleware callback needs.
# ------------------------------------------------------------------------
def test_logged_out_visit_redirects_to_keycloak(page: Page, ui_timeout_ms: int):
    log_header("Marva logged-out visit redirects to Keycloak")
    page.goto(f"{marva_url()}/", wait_until="domcontentloaded", timeout=ui_timeout_ms)
    try:
        page.wait_for_url(f"**{KEYCLOAK_AUTH_PATH}**", timeout=15_000)
    except PlaywrightTimeoutError:
        pytest.skip(
            f"Marva stayed on {page.url}; this build predates the logged-out SSO "
            "redirect. Build Marva from a branch (--marva-ref / --dev-mode) to run it."
        )

    query = parse_qs(urlparse(page.url).query)
    redirect_uri = query.get("redirect_uri", [""])[0]
    log_expected_actual("redirect_uri", f"...{MIDDLEWARE_CALLBACK_PATH}", redirect_uri)
    assert redirect_uri.endswith(MIDDLEWARE_CALLBACK_PATH)
    assert query.get("client_id", [""])[0], "SSO redirect is missing client_id"
    assert query.get("state", [""])[0], "SSO redirect is missing state"
    expect(page.locator("#username")).to_be_visible(timeout=ui_timeout_ms)
    expect(page.locator("#password")).to_be_visible()


# ========================================================================
# Wrong credentials are rejected: Keycloak keeps the user on its login page
# and Marva never receives a token.
# ------------------------------------------------------------------------
def test_invalid_credentials_are_rejected(page: Page, ui_timeout_ms: int):
    log_header("Marva rejects invalid credentials")
    _open_login(page, ui_timeout_ms)
    page.locator("#username").fill(keycloak_username())
    page.locator("#password").fill("definitely-the-wrong-password")
    page.locator("#kc-login").click()

    expect(page.locator("#kc-login")).to_be_visible(timeout=ui_timeout_ms)
    expect(page.locator("#password")).to_be_visible()
    log_expected_actual("still on Keycloak realm", True, "/realms/bluecore/" in page.url)
    assert "/realms/bluecore/" in page.url


# ========================================================================
# Full SSO round trip: log in via Keycloak, land back with a token, log out.
# ------------------------------------------------------------------------
def test_full_sso_login_and_logout(page: Page, ui_timeout_ms: int):
    log_header("Marva full SSO login and logout")
    _login(page, ui_timeout_ms)

    has_token = bool(page.evaluate("() => window.localStorage.getItem('marva_jwt')"))
    log_expected_actual("marva_jwt saved after login", True, has_token)
    assert has_token
    # The token is moved into storage, not left in the address bar.
    assert "token=" not in page.url

    # The nav's account item (user icon + name) opens the Account modal with Logout.
    page.get_by_text("account_circle", exact=True).first.click()
    page.get_by_role("link", name="Logout").click()
    page.wait_for_url("**/realms/bluecore/protocol/openid-connect/logout**", timeout=ui_timeout_ms)

    has_token = bool(page.evaluate("() => window.localStorage.getItem('marva_jwt')"))
    log_expected_actual("marva_jwt cleared after logout", False, has_token)
    assert not has_token


# ========================================================================
# After login the home page renders its main panels and nav menus.
# ------------------------------------------------------------------------
def test_home_page_renders_after_login(authenticated_page: Page, ui_timeout_ms: int):
    log_header("Marva home renders after login")
    page = authenticated_page
    expect(page).to_have_title("Marva", timeout=ui_timeout_ms)
    expect(page.get_by_placeholder("URL to resource or identifier to search")).to_be_visible(
        timeout=ui_timeout_ms
    )
    expect(page.get_by_text("Records", exact=True).first).to_be_visible()
    for menu in ("Menu", "Tools", "View", "Preferences"):
        expect(page.get_by_text(menu, exact=True).first).to_be_visible()


# ========================================================================
# Logging in and loading the home page raises no uncaught JS errors or
# same-origin 5xx responses. Catches a broken bundle or failing boot request.
# ------------------------------------------------------------------------
def test_home_page_loads_without_errors(page: Page, page_signals, ui_timeout_ms: int):
    log_header("Marva home loads without errors")
    _login(page, ui_timeout_ms)
    expect(page.get_by_placeholder("URL to resource or identifier to search")).to_be_visible(
        timeout=ui_timeout_ms
    )

    log_expected_actual("uncaught JS errors", [], page_signals.page_errors)
    assert page_signals.page_errors == [], (
        f"Uncaught browser errors on load: {page_signals.page_errors}"
    )
    # Marva's /marva/util/* calls other than /auth/ are proxied to LC's util
    # backend (MARVA_UTIL_PATH), which Blue Core doesn't run, so they 502 here.
    server_errors = [
        error
        for error in page_signals.server_errors
        if "/marva/util/" not in error or "/marva/util/auth/" in error
    ]
    log_expected_actual("same-origin 5xx responses", [], server_errors)
    assert server_errors == [], f"Server errors while loading Marva: {server_errors}"


# ========================================================================
# A blank record template opens in the editor with the Post button.
# ------------------------------------------------------------------------
def test_blank_record_opens_editor(authenticated_page: Page, ui_timeout_ms: int):
    log_header("Marva opens a blank record")
    page = authenticated_page
    _open_blank_monograph(page, ui_timeout_ms)

    page.get_by_text("Menu", exact=True).first.click()
    expect(page.locator("#post-button")).to_be_attached(timeout=ui_timeout_ms)


# ========================================================================
# Export to Catalog (marva_editor#30) is in the editor menu, and on a record
# that wasn't loaded from Blue Core it explains why it can't export yet,
# without calling the API.
# ------------------------------------------------------------------------
def test_export_to_catalog_needs_a_blue_core_record(
    authenticated_page: Page, ui_timeout_ms: int
):
    log_header("Marva Export to Catalog on an unposted record")
    page = authenticated_page
    _open_blank_monograph(page, ui_timeout_ms)
    page.get_by_text("Menu", exact=True).first.click()

    export = page.locator("#bluecore-export-button")
    try:
        export.wait_for(state="attached", timeout=5_000)
    except PlaywrightTimeoutError:
        pytest.skip(
            "This Marva build has no Export to Catalog menu item yet (marva_editor#30). "
            "Build Marva from a branch (--marva-ref / --dev-mode) to run it."
        )

    export_requests: list[str] = []
    page.on(
        "request",
        lambda request: export_requests.append(request.url) if "/export/" in request.url else None,
    )

    # The alert blocks the page until it's closed, so record and dismiss it.
    messages: list[str] = []
    page.once("dialog", lambda dialog: (messages.append(dialog.message), dialog.dismiss()))
    export.click()
    for _ in range(50):
        if messages:
            break
        page.wait_for_timeout(100)
    message = messages[0] if messages else ""

    log_expected_actual("alert explains the Blue Core requirement", True, "loaded from Blue Core" in message)
    assert "only available for Instances loaded from Blue Core" in message
    assert export_requests == [], f"Export was sent for an unposted record: {export_requests}"
