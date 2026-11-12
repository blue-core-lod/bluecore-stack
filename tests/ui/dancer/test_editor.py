from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

import pytest
from playwright.sync_api import Page, expect

from tests.integration.support.logging import log_expected_actual, log_header
from tests.ui._support import KEYCLOAK_AUTH_PATH, full_stack_enabled, keycloak_username
from tests.ui.dancer._support import (
    SEEDED_WORKSPACE,
    dancer_url,
    login_to_dancer,
    submit_keycloak_login,
    temp_workspace_name,
    workspace_card,
)

# Real-browser tests for the DCTap Dancer (Marva's template editor) through
# Nginx: Keycloak login, the workspace list, opening the seeded "Blue Core"
# workspace and its shapes, creating and downloading a workspace, and logout.
# Tests that change data only use temporary workspaces, deleted afterwards.
# Marva's side (loading profiles from the dancer) is in tests/ui/marva/test_dancer.py.
pytestmark = pytest.mark.skipif(
    not full_stack_enabled(),
    reason="DCTap Dancer UI tests require the full stack (Nginx + Marva + DCTap Dancer)",
)


def _open_workspace(page: Page, name: str, timeout: int) -> str:
    """Open a workspace from the home page and return its ID (from the URL)."""
    workspace_card(page, name).get_by_role("button", name="Open").click()
    page.wait_for_url(f"{dancer_url()}/workspace/**", timeout=timeout)
    expect(page.locator(".workspace-header h1")).to_contain_text(name, timeout=timeout)
    return urlparse(page.url).path.rstrip("/").split("/workspace/")[1].split("/")[0]


def _select_first_shape(page: Page, timeout: int) -> str:
    """
    Expand the first folder (seeded folders start collapsed), select its first
    shape, and wait for the grid. Returns the shape's ID.
    """
    folder = page.locator(".folder-container").first
    folder.locator(".folder-header").click()
    shape = folder.locator(".shape-item").first
    expect(shape).to_be_visible(timeout=timeout)
    shape_id = shape.locator(".shape-name").inner_text()
    shape.click()
    page.wait_for_url(re.compile(r"/workspace/[^/]+/shape/"), timeout=timeout)
    expect(page.locator("table.grid")).to_be_visible(timeout=timeout)
    return shape_id


# ========================================================================
# A logged-out visit goes straight to Blue Core's Keycloak login, using the
# bluecore_api client with PKCE and coming back to the dancer.
# ------------------------------------------------------------------------
def test_logged_out_visit_redirects_to_keycloak(page: Page, ui_timeout_ms: int):
    log_header("DCTap Dancer logged-out visit redirects to Keycloak")
    page.goto(f"{dancer_url()}/", wait_until="domcontentloaded", timeout=ui_timeout_ms)
    page.wait_for_url(f"**{KEYCLOAK_AUTH_PATH}**", timeout=ui_timeout_ms)

    query = parse_qs(urlparse(page.url).query)
    redirect_uri = query.get("redirect_uri", [""])[0]
    log_expected_actual("redirect_uri", f"{dancer_url()}/…", redirect_uri)
    assert redirect_uri.startswith(f"{dancer_url()}/")
    assert query.get("client_id", [""])[0] == "bluecore_api"
    assert query.get("code_challenge_method", [""])[0] == "S256", (
        "Login is not using PKCE"
    )
    expect(page.locator("#username")).to_be_visible(timeout=ui_timeout_ms)


# ========================================================================
# Wrong credentials keep the user on the Keycloak login page.
# ------------------------------------------------------------------------
def test_invalid_credentials_are_rejected(page: Page, ui_timeout_ms: int):
    log_header("DCTap Dancer rejects invalid credentials")
    page.goto(f"{dancer_url()}/", wait_until="domcontentloaded", timeout=ui_timeout_ms)
    page.wait_for_url(f"**{KEYCLOAK_AUTH_PATH}**", timeout=ui_timeout_ms)
    page.locator("#username").fill(keycloak_username())
    page.locator("#password").fill("definitely-the-wrong-password")
    page.locator("#kc-login").click()

    expect(page.locator("#kc-login")).to_be_visible(timeout=ui_timeout_ms)
    log_expected_actual("still on Keycloak", True, "/realms/bluecore/" in page.url)
    assert "/realms/bluecore/" in page.url
    assert not page.url.startswith(dancer_url())


# ========================================================================
# Logging in returns to the dancer with a clean address bar (no leftover
# #state=…&code=…) and shows who is signed in.
# ------------------------------------------------------------------------
def test_login_returns_with_a_clean_url_and_shows_the_user(
    page: Page, ui_timeout_ms: int
):
    log_header("DCTap Dancer login")
    login_to_dancer(page, ui_timeout_ms)

    log_expected_actual("URL after login", f"{dancer_url()}/", page.url)
    assert page.url == f"{dancer_url()}/"
    expect(page.locator(".bluecore-user-bar")).to_contain_text(
        f"Signed in as {keycloak_username()}"
    )


# ========================================================================
# The home page lists the seeded workspace.
# ------------------------------------------------------------------------
def test_home_lists_the_seeded_workspace(page: Page, ui_timeout_ms: int):
    log_header("DCTap Dancer home lists the seeded workspace")
    login_to_dancer(page, ui_timeout_ms)
    expect(page.get_by_role("heading", name="DCTap Dancer")).to_be_visible()
    expect(workspace_card(page, SEEDED_WORKSPACE)).to_be_visible(timeout=ui_timeout_ms)


# ========================================================================
# Opening the seeded workspace shows its folders and shapes, and selecting
# a shape fills the grid with its rows.
# ------------------------------------------------------------------------
def test_open_seeded_workspace_and_browse_a_shape(page: Page, ui_timeout_ms: int):
    log_header("DCTap Dancer opens the seeded workspace")
    login_to_dancer(page, ui_timeout_ms)
    _open_workspace(page, SEEDED_WORKSPACE, ui_timeout_ms)

    folders = page.locator(".folder-name")
    expect(folders.first).to_be_visible(timeout=ui_timeout_ms)
    log_expected_actual("profile folders listed", "> 0", folders.count())
    assert folders.count() > 0, "Seeded profiles should be grouped in folders"

    shape_id = _select_first_shape(page, ui_timeout_ms)
    expect(page.get_by_text(shape_id, exact=True).last).to_be_visible()
    log_expected_actual(
        f"rows in '{shape_id}'", "> 0", page.locator(".row-number").count()
    )
    assert page.locator(".row-number").count() > 0


# ========================================================================
# A bookmarked workspace link survives the login round trip: after Keycloak
# the user lands on that workspace, not the home page.
# ------------------------------------------------------------------------
def test_deep_link_survives_login(page: Page, ui_timeout_ms: int, dancer_api):
    log_header("DCTap Dancer deep link survives login")
    seeded_id = dancer_api.seeded_workspace()["id"]
    login_to_dancer(page, ui_timeout_ms, path=f"/workspace/{seeded_id}")

    expected = f"{dancer_url()}/workspace/{seeded_id}"
    log_expected_actual("URL after login", expected, page.url)
    assert page.url == expected
    expect(page.locator(".workspace-header h1")).to_contain_text(SEEDED_WORKSPACE)


# ========================================================================
# A workspace created from the home page opens in the editor and is listed
# when going back home.
# ------------------------------------------------------------------------
def test_create_a_workspace_from_the_home_page(
    page: Page, ui_timeout_ms: int, dancer_api
):
    log_header("DCTap Dancer creates a workspace")
    name = temp_workspace_name()
    login_to_dancer(page, ui_timeout_ms)

    page.get_by_role("button", name="New Workspace").click()
    page.locator("#name").fill(name)
    page.get_by_role("button", name="Create").click()
    page.wait_for_url(f"{dancer_url()}/workspace/**", timeout=ui_timeout_ms)
    dancer_api.track(urlparse(page.url).path.rstrip("/").split("/workspace/")[1])
    expect(page.locator(".workspace-header h1")).to_contain_text(
        name, timeout=ui_timeout_ms
    )

    page.get_by_title("Back to Home").click()
    expect(workspace_card(page, name)).to_be_visible(timeout=ui_timeout_ms)


# ========================================================================
# Download (a link the browser opens directly) is authenticated by the
# token cookie and saves the workspace's .db file.
# ------------------------------------------------------------------------
def test_download_a_workspace(page: Page, ui_timeout_ms: int, dancer_api):
    log_header("DCTap Dancer downloads a workspace")
    workspace = dancer_api.create()
    login_to_dancer(page, ui_timeout_ms)

    card = workspace_card(page, workspace["name"])
    expect(card).to_be_visible(timeout=ui_timeout_ms)
    with page.expect_download(timeout=ui_timeout_ms) as download_info:
        card.get_by_text("Download", exact=True).click()
    download = download_info.value

    log_expected_actual("downloaded file", "<name>.db", download.suggested_filename)
    assert download.suggested_filename.endswith(".db")
    assert download.failure() is None


# ========================================================================
# Log out ends the session: the token cookie is cleared and the next visit
# needs the Keycloak login again.
# ------------------------------------------------------------------------
def test_log_out(page: Page, ui_timeout_ms: int):
    log_header("DCTap Dancer log out")
    login_to_dancer(page, ui_timeout_ms)

    page.locator(".bluecore-user-bar").get_by_role("button", name="Log out").click()
    page.wait_for_url(f"**{KEYCLOAK_AUTH_PATH}**", timeout=ui_timeout_ms)
    expect(page.locator("#username")).to_be_visible(timeout=ui_timeout_ms)

    cookies = [
        c["name"] for c in page.context.cookies() if c["name"] == "dancer_access_token"
    ]
    log_expected_actual("token cookie after logout", [], cookies)
    assert cookies == []

    submit_keycloak_login(page, ui_timeout_ms)
    page.wait_for_url(f"{dancer_url()}/**", timeout=ui_timeout_ms)
    expect(page.locator(".bluecore-user-bar")).to_be_visible(timeout=ui_timeout_ms)


# ========================================================================
# Logging in, opening the seeded workspace and a shape raise no uncaught
# JS errors or same-origin 5xx responses.
# ------------------------------------------------------------------------
def test_editor_loads_without_errors(page: Page, page_signals, ui_timeout_ms: int):
    log_header("DCTap Dancer loads without errors")
    login_to_dancer(page, ui_timeout_ms)
    _open_workspace(page, SEEDED_WORKSPACE, ui_timeout_ms)
    _select_first_shape(page, ui_timeout_ms)

    log_expected_actual("uncaught JS errors", [], page_signals.page_errors)
    assert page_signals.page_errors == [], (
        f"Uncaught browser errors: {page_signals.page_errors}"
    )
    log_expected_actual("same-origin 5xx responses", [], page_signals.server_errors)
    assert page_signals.server_errors == [], (
        f"Server errors: {page_signals.server_errors}"
    )
