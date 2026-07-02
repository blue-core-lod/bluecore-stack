from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

import pytest
from playwright.sync_api import Page, expect

from tests.integration.support.logging import log_expected_actual, log_header
from tests.ui._support import (
    KEYCLOAK_AUTH_PATH,
    full_stack_enabled,
    keycloak_password,
    keycloak_username,
    sinopia_url,
)

# Real-browser tests for the Sinopia editor. They drive Chromium (via the
# pytest-playwright `page` fixture) through Nginx, so they need the full stack.
# The runner enables it by default (INTEGRATION_FULL_STACK=1); skip cleanly when
# a lightweight run omits Nginx/Sinopia.
# tests/integration/sinopia cover the API surface in every mode.
#
# ==============================================================================
# Why the authenticated tests skip outside dev-mode
# ------------------------------------------------------------------------------
# Sinopia's frontend config (including its own `sinopiaUrl`) is compiled INTO
# the JavaScript bundle at build time.
#
#   * Non-dev-mode runs the PUBLISHED Sinopia image, whose bundle was built with
#     the PRODUCTION url (https://dev.bcld.info/sinopia). After a successful
#     Keycloak login the SSO redirect goes to `sinopiaUrl`, i.e. production, so
#     the browser leaves the local stack and the authenticated editor never
#     renders locally. Any test that needs a completed login (the full SSO round
#     trip and everything using the `authenticated_page` fixture) SKIPS with a
#     "Post-login redirect left the local stack" message.
#
#   * Dev-mode runs Sinopia from LOCAL source with LOCAL urls
#     (SINOPIA_URI=http://localhost/sinopia, wired in
#     compose-integration-test-dev-mode.yaml), so the redirect stays local and
#     these tests RUN. Use: ./scripts/test/integration-tests.sh --dev-mode
#     tests/ui/sinopia
#
# The unauthenticated tests (load, login panel, SSO redirect, OAuth params,
# invalid credentials) run in BOTH modes because they never complete a login.
# ------------------------------------------------------------------------------
pytestmark = pytest.mark.skipif(
    not full_stack_enabled(),
    reason="Sinopia UI tests require the full stack (Nginx + Sinopia)",
)


def _open_editor(page: Page, timeout: int) -> None:
    page.goto(f"{sinopia_url()}/", wait_until="domcontentloaded", timeout=timeout)


def _login(page: Page, timeout: int) -> bool:
    """
    Run the Keycloak SSO login from the editor.
    Returns True only if the post-login redirect returned to the LOCAL Sinopia
    origin. Sinopia bakes its `sinopiaUrl` into the bundle at build time, so the
    published image (used outside dev-mode) redirects to production after login
    and this returns False. Callers use the result to skip authenticated
    assertions that are only meaningful on the local stack. See the module
    docstring above for the full explanation.
    """
    _open_editor(page, timeout)
    page.get_by_role("button", name="Login").click()
    page.wait_for_url(f"**{KEYCLOAK_AUTH_PATH}**", timeout=timeout)
    page.locator("#username").fill(keycloak_username())
    page.locator("#password").fill(keycloak_password())
    page.locator("#kc-login").click()
    page.wait_for_url(lambda url: KEYCLOAK_AUTH_PATH not in url, timeout=timeout)
    return page.url.startswith(sinopia_url())


def _enter_editor(page: Page, timeout: int) -> None:
    """
    From the authenticated home page, enter the app (the Dashboard).
    The home header only exposes a "Linked Data Editor" link; the Dashboard /
    Resource Templates tab nav appears on the in-app pages.
    """
    page.get_by_role("link", name="Linked Data Editor").click()
    page.wait_for_url("**/sinopia/dashboard", timeout=timeout)


@pytest.fixture
def authenticated_page(page: Page, ui_timeout_ms: int) -> Page:
    """
    A page logged into the editor, or a skip when login left the local stack.
    Tests using this fixture exercise the authenticated editor, so they only run
    when Sinopia is served with local urls (dev-mode / local-source build). On
    the published-image stack the post-login redirect goes to production, and the
    fixture skips the test. See the module docstring for why.
    """
    if not _login(page, ui_timeout_ms):
        pytest.skip(
            f"Post-login redirect left the local stack ({page.url}); the published "
            "Sinopia image bakes a non-local sinopiaUrl. Run Sinopia from local source "
            "(dev-mode) to exercise the authenticated editor."
        )
    return page


# ========================================================================
# The editor page loads its HTML shell and mounts the React app.
# ------------------------------------------------------------------------
def test_editor_loads(page: Page, ui_timeout_ms: int):
    log_header("Sinopia editor loads")
    _open_editor(page, ui_timeout_ms)
    # The Blue Core fork sets the runtime title (e.g. "Sinopia - bluecore"), so
    # match on the product name rather than the static index.html title.
    expect(page).to_have_title(re.compile(r"Sinopia", re.IGNORECASE), timeout=ui_timeout_ms)
    # index.js mounts RootContainer into a div.container-fluid appended to body.
    expect(page.locator("div.container-fluid").first).to_be_visible(timeout=ui_timeout_ms)


# ========================================================================
# When unauthenticated, the editor shows its login panel.
# ------------------------------------------------------------------------
def test_login_panel_present_when_unauthenticated(page: Page, ui_timeout_ms: int):
    log_header("Sinopia login panel present")
    _open_editor(page, ui_timeout_ms)
    expect(
        page.get_by_role("heading", name="Login to the Linked Data Editor")
    ).to_be_visible(timeout=ui_timeout_ms)
    expect(page.get_by_role("button", name="Login")).to_be_visible()


# ========================================================================
# Clicking Login sends the browser through the Keycloak SSO redirect.
# ------------------------------------------------------------------------
def test_login_redirects_to_keycloak(page: Page, ui_timeout_ms: int):
    log_header("Sinopia login redirects to Keycloak")
    _open_editor(page, ui_timeout_ms)
    page.get_by_role("button", name="Login").click()

    page.wait_for_url(f"**{KEYCLOAK_AUTH_PATH}**", timeout=ui_timeout_ms)
    log_expected_actual("on Keycloak auth page", True, KEYCLOAK_AUTH_PATH in page.url)
    # Keycloak's login form fields are stable across themes.
    expect(page.locator("#username")).to_be_visible(timeout=ui_timeout_ms)
    expect(page.locator("#password")).to_be_visible()


# ========================================================================
# Full SSO round trip: log in via Keycloak, land back authenticated, log out.
# ------------------------------------------------------------------------
def test_full_sso_login_and_logout(page: Page, ui_timeout_ms: int):
    log_header("Sinopia full SSO login and logout")
    # The published Sinopia image bakes its production URL into the bundle, so on
    # that stack the post-login redirect leaves the local origin; skip then. It
    # runs fully when Sinopia is served with local URLs (local-source build).
    if not _login(page, ui_timeout_ms):
        pytest.skip(
            f"Sinopia redirected to {page.url} after SSO instead of {sinopia_url()}; "
            "the published image is built with a non-local sinopiaUrl."
        )

    # Back in the local editor and authenticated: the header exposes logout.
    logout = page.locator(".editor-header-logout").first
    expect(logout).to_be_visible(timeout=ui_timeout_ms)

    logout.click()
    # Logging out returns the editor to its unauthenticated login panel.
    expect(
        page.get_by_role("heading", name="Login to the Linked Data Editor")
    ).to_be_visible(timeout=ui_timeout_ms)


# ========================================================================
# The editor loads without uncaught JS errors or same-origin 5xx responses.
# High-signal regression guard: a broken bundle, failed boot request, or a
# 500 from the API on load will fail this.
# ------------------------------------------------------------------------
def test_editor_loads_without_errors(page: Page, page_signals, ui_timeout_ms: int):
    log_header("Sinopia editor loads without errors")
    _open_editor(page, ui_timeout_ms)
    # Wait for a rendered control so late boot errors are captured too.
    expect(page.get_by_role("button", name="Login")).to_be_visible(timeout=ui_timeout_ms)

    log_expected_actual("uncaught JS errors", [], page_signals.page_errors)
    assert page_signals.page_errors == [], (
        f"Uncaught browser errors on load: {page_signals.page_errors}"
    )
    log_expected_actual("same-origin 5xx responses", [], page_signals.server_errors)
    assert page_signals.server_errors == [], (
        f"Server errors while loading the editor: {page_signals.server_errors}"
    )


# ========================================================================
# The SPA renders real content (bundle executed), not just an empty shell.
# ------------------------------------------------------------------------
def test_home_page_renders_content(page: Page, ui_timeout_ms: int):
    log_header("Sinopia home renders content")
    _open_editor(page, ui_timeout_ms)
    # Blue Core branding is present in the rendered home page.
    expect(
        page.get_by_role("heading", name=re.compile(r"Blue Core", re.IGNORECASE)).first
    ).to_be_visible(timeout=ui_timeout_ms)
    # And the interactive login control rendered.
    expect(page.get_by_role("button", name="Login")).to_be_visible()


# ========================================================================
# The SSO redirect carries the OAuth parameters Keycloak needs, against the
# bluecore realm. Catches client/realm/flow misconfiguration.
# ------------------------------------------------------------------------
def test_login_redirect_has_expected_oauth_params(page: Page, ui_timeout_ms: int):
    log_header("Sinopia SSO redirect OAuth params")
    _open_editor(page, ui_timeout_ms)
    page.get_by_role("button", name="Login").click()
    page.wait_for_url(f"**{KEYCLOAK_AUTH_PATH}**", timeout=ui_timeout_ms)

    query = parse_qs(urlparse(page.url).query)
    assert "/realms/bluecore/protocol/openid-connect/auth" in page.url

    response_type = query.get("response_type", [""])[0]
    log_expected_actual("response_type contains 'code'", True, "code" in response_type)
    assert "code" in response_type

    assert query.get("client_id", [""])[0], "SSO redirect is missing client_id"
    assert query.get("redirect_uri", [""])[0], "SSO redirect is missing redirect_uri"
    assert query.get("scope", [""])[0], "SSO redirect is missing scope"


# ========================================================================
# Wrong credentials are rejected: Keycloak keeps the user on its login page
# and does not authenticate. Guards the auth path against regressions.
# ------------------------------------------------------------------------
def test_invalid_credentials_are_rejected(page: Page, ui_timeout_ms: int):
    log_header("Sinopia rejects invalid credentials")
    _open_editor(page, ui_timeout_ms)
    page.get_by_role("button", name="Login").click()
    page.wait_for_url(f"**{KEYCLOAK_AUTH_PATH}**", timeout=ui_timeout_ms)

    page.locator("#username").fill(keycloak_username())
    page.locator("#password").fill("definitely-the-wrong-password")
    page.locator("#kc-login").click()

    # Still on the Keycloak login form (not redirected back to the app).
    expect(page.locator("#kc-login")).to_be_visible(timeout=ui_timeout_ms)
    expect(page.locator("#password")).to_be_visible()
    log_expected_actual("still on Keycloak realm", True, "/realms/bluecore/" in page.url)
    assert "/realms/bluecore/" in page.url


# ========================================================================
# Authenticated shell renders: user identity, logout, and primary nav.
# ------------------------------------------------------------------------
def test_authenticated_header_shows_user_and_nav(
    authenticated_page: Page, ui_timeout_ms: int
):
    log_header("Sinopia authenticated header and nav")
    page = authenticated_page
    # Authenticated home header: user identity, logout, and the app entry link.
    expect(page.locator(".editor-header-user")).to_be_visible(timeout=ui_timeout_ms)
    expect(page.locator(".editor-header-logout")).to_be_visible()
    expect(page.get_by_role("link", name="Linked Data Editor")).to_be_visible()


# ========================================================================
# Entering the app lands on the Dashboard, which renders its content.
# ------------------------------------------------------------------------
def test_navigate_to_dashboard(authenticated_page: Page, ui_timeout_ms: int):
    log_header("Sinopia navigate to Dashboard")
    page = authenticated_page
    _enter_editor(page, ui_timeout_ms)
    # A fresh user sees the empty-state "Welcome to Sinopia."; an active user
    # sees "Recent ..." sections. Match either so the test is data-independent.
    expect(
        page.get_by_role(
            "heading", name=re.compile(r"Welcome to Sinopia|Recent", re.IGNORECASE)
        ).first
    ).to_be_visible(timeout=ui_timeout_ms)


# ========================================================================
# The Resource Templates page loads (the Sinopia<->Blue Core template surface).
# ------------------------------------------------------------------------
def test_navigate_to_resource_templates(authenticated_page: Page, ui_timeout_ms: int):
    log_header("Sinopia navigate to Resource Templates")
    page = authenticated_page
    _enter_editor(page, ui_timeout_ms)
    page.get_by_role("link", name="Resource Templates").click()
    page.wait_for_url("**/sinopia/templates", timeout=ui_timeout_ms)
    expect(page.locator("#resourceTemplate")).to_be_visible(timeout=ui_timeout_ms)
    expect(
        page.get_by_placeholder("Enter id, label, URI, remark, group, or author")
    ).to_be_visible()


# ========================================================================
# Authenticated pages (more API traffic) load without JS errors or 5xx.
# ------------------------------------------------------------------------
def test_authenticated_pages_load_without_errors(
    page: Page, page_signals, ui_timeout_ms: int
):
    log_header("Sinopia authenticated pages load without errors")
    if not _login(page, ui_timeout_ms):
        pytest.skip(
            f"Post-login redirect left the local stack ({page.url}); "
            "run Sinopia from local source (dev-mode)."
        )

    _enter_editor(page, ui_timeout_ms)
    # A fresh user sees the empty-state "Welcome to Sinopia."; an active user
    # sees "Recent ..." sections. Match either so the test is data-independent.
    expect(
        page.get_by_role(
            "heading", name=re.compile(r"Welcome to Sinopia|Recent", re.IGNORECASE)
        ).first
    ).to_be_visible(timeout=ui_timeout_ms)

    page.get_by_role("link", name="Resource Templates").click()
    page.wait_for_url("**/sinopia/templates", timeout=ui_timeout_ms)
    expect(page.locator("#resourceTemplate")).to_be_visible(timeout=ui_timeout_ms)

    assert page_signals.page_errors == [], (
        f"Uncaught browser errors on authenticated pages: {page_signals.page_errors}"
    )
    assert page_signals.server_errors == [], (
        f"Server errors on authenticated pages: {page_signals.server_errors}"
    )
