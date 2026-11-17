from __future__ import annotations

import base64
import json
import time

import pytest
from playwright.sync_api import Page, Route, expect

from tests.integration.support.logging import log_expected_actual, log_header
from tests.ui._support import KEYCLOAK_AUTH_PATH, bluecore_url, full_stack_enabled
from tests.ui.dancer._support import submit_keycloak_login

# Real-browser tests for the Marva login page (nginx/marva-login/): it has the
# same Blue Core header and footer as Marva, and a user who is already signed
# in to Marva goes straight to Marva instead of seeing it
# (nginx/assets/bluecore/marva-login.js).
pytestmark = pytest.mark.skipif(
    not full_stack_enabled(),
    reason="Marva login page UI tests require the full stack (Nginx + Marva + Keycloak)",
)

APPS = ["Search", "Marva", "Sinopia", "Graph Toolbox", "API", "Keycloak", "Workflows"]


def login_page_url() -> str:
    return f"{bluecore_url()}/marva-login/"


def marva_url() -> str:
    return f"{bluecore_url()}/marva/"


def _fake_jwt(**claims: object) -> str:
    """A token Marva's pages can decode (they don't check the signature)."""

    def part(data: dict) -> str:
        raw = json.dumps(data).encode()
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    return f"{part({'alg': 'none'})}.{part(claims)}.sig"


def _with_marva_token(page: Page, token: str) -> None:
    """Put a Marva token in localStorage before any page script runs."""
    page.add_init_script(
        f"window.localStorage.setItem('marva_jwt', {json.dumps(token)})"
    )


def _stub_marva(page: Page) -> None:
    """Answer /marva/ with a blank page, so only the redirect itself is tested."""

    def fulfill(route: Route) -> None:
        route.fulfill(status=200, content_type="text/html", body="<p>stub marva</p>")

    page.route(marva_url(), fulfill)


# ========================================================================
# Signed out: the page shows the Blue Core header and footer and a Login link.
# ------------------------------------------------------------------------
def test_signed_out_shows_bluecore_header_footer_and_login(
    page: Page, ui_timeout_ms: int
):
    log_header("Marva login page, signed out")
    page.goto(login_page_url(), timeout=ui_timeout_ms)

    header = page.locator("header.bluecore-header")
    expect(header).to_be_visible()
    expect(header.locator(".bluecore-header-app-name")).to_contain_text("MARVA")
    expect(page.locator(".bluecore-logo").first).to_be_visible()

    # "Switch applications" opens a menu of every app but Marva, Escape closes it
    menu = page.locator("#bluecore-app-menu")
    expect(menu).to_be_hidden()
    header.get_by_role("button", name="Switch applications").click()
    expect(menu).to_be_visible()
    expect(menu.get_by_role("link")).to_have_text([a for a in APPS if a != "Marva"])
    page.keyboard.press("Escape")
    expect(menu).to_be_hidden()

    footer = page.locator("footer.bluecore-footer")
    expect(footer).to_be_visible()
    expect(footer.locator(".bluecore-footer-app-list a")).to_have_text(APPS)

    login = page.get_by_role("link", name="Login", exact=True)
    expect(login).to_have_attribute("href", "/marva/")
    log_expected_actual("URL", login_page_url(), page.url)
    assert page.url == login_page_url()


# ========================================================================
# A Marva token that hasn't expired sends the user straight to Marva. (This
# fake token has no Keycloak session id, so the page trusts its expiry.)
# ------------------------------------------------------------------------
def test_unexpired_token_goes_straight_to_marva(page: Page, ui_timeout_ms: int):
    log_header("Marva login page, unexpired token")
    _stub_marva(page)
    _with_marva_token(page, _fake_jwt(exp=int(time.time()) + 3600))

    page.goto(login_page_url(), timeout=ui_timeout_ms)
    page.wait_for_url(marva_url(), timeout=ui_timeout_ms)
    log_expected_actual("URL", marva_url(), page.url)
    assert page.url == marva_url()


# ========================================================================
# An expired token (and no Keycloak session to check) shows the login page.
# ------------------------------------------------------------------------
def test_expired_token_shows_the_login_page(page: Page, ui_timeout_ms: int):
    log_header("Marva login page, expired token")
    _stub_marva(page)
    _with_marva_token(page, _fake_jwt(exp=int(time.time()) - 60))

    page.goto(login_page_url(), timeout=ui_timeout_ms)
    expect(page.get_by_role("link", name="Login", exact=True)).to_be_visible(
        timeout=ui_timeout_ms
    )
    log_expected_actual("URL", login_page_url(), page.url)
    assert page.url == login_page_url()


# ========================================================================
# After a real Keycloak login to Marva, the login page checks the Keycloak
# session and goes straight back to Marva without asking to log in again.
# ------------------------------------------------------------------------
def test_signed_in_user_skips_the_login_page(page: Page, ui_timeout_ms: int):
    log_header("Marva login page, signed in through Keycloak")
    page.goto(marva_url(), wait_until="domcontentloaded", timeout=ui_timeout_ms)
    submit_keycloak_login(page, ui_timeout_ms)
    page.wait_for_url(f"{marva_url()}**", timeout=ui_timeout_ms)
    page.wait_for_function(
        "() => !!window.localStorage.getItem('marva_jwt')", timeout=ui_timeout_ms
    )

    page.goto(login_page_url(), timeout=ui_timeout_ms)
    page.wait_for_url(f"{marva_url()}**", timeout=ui_timeout_ms)
    log_expected_actual("URL", f"{marva_url()}…", page.url)
    assert page.url.startswith(marva_url())
    assert KEYCLOAK_AUTH_PATH not in page.url


# ========================================================================
# Logging out of Marva (its Logout goes to /marva/util/auth/logout) ends the
# Keycloak session without Keycloak's "Do you want to log out?" page and lands
# on the Marva login page, which stays put now that the session is gone.
# Needs http://localhost/marva-login/ in the bluecore_api client's valid post
# logout redirect URIs (keycloak-export/development/bluecore-realm.json).
# ------------------------------------------------------------------------
def test_logout_lands_on_the_login_page(page: Page, ui_timeout_ms: int):
    log_header("Marva logout returns to the Marva login page")
    page.goto(marva_url(), wait_until="domcontentloaded", timeout=ui_timeout_ms)
    submit_keycloak_login(page, ui_timeout_ms)
    page.wait_for_url(f"{marva_url()}**", timeout=ui_timeout_ms)
    page.wait_for_function(
        "() => !!window.localStorage.getItem('marva_jwt')", timeout=ui_timeout_ms
    )

    page.evaluate("() => window.localStorage.removeItem('marva_jwt')")
    page.goto(f"{marva_url()}util/auth/logout", timeout=ui_timeout_ms)
    page.wait_for_url(login_page_url(), timeout=ui_timeout_ms)
    log_expected_actual("URL after logout", login_page_url(), page.url)
    assert page.url == login_page_url()
    expect(page.get_by_role("link", name="Login", exact=True)).to_be_visible(
        timeout=ui_timeout_ms
    )

    # the Keycloak session really ended: Marva asks for the Keycloak login again
    page.goto(marva_url(), wait_until="domcontentloaded", timeout=ui_timeout_ms)
    page.wait_for_url(f"**{KEYCLOAK_AUTH_PATH}**", timeout=ui_timeout_ms)
    expect(page.locator("#username")).to_be_visible(timeout=ui_timeout_ms)
