from __future__ import annotations

import os
import re

import pytest
from playwright.sync_api import Page, Response, expect
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from tests.integration.support.logging import log_expected_actual, log_header
from tests.ui._support import KEYCLOAK_AUTH_PATH, bluecore_url, full_stack_enabled
from tests.ui.dancer._support import SEEDED_WORKSPACE, dancer_url, submit_keycloak_login

# Real-browser tests for Marva's side of the DCTap Dancer: Marva loads its
# profiles and starting points from a dancer workspace ("Blue Core" by
# default), the DCTap menu switches workspaces, and "Edit Templates" opens the
# dancer. The dancer's own UI is tested in tests/ui/dancer.
#
# These need a Marva build with the Blue Core dancer integration. Older
# builds (e.g. a published `:latest` that predates it) SKIP; build Marva from a
# branch to run them: --marva-ref <branch> or --dev-mode.
pytestmark = pytest.mark.skipif(
    not full_stack_enabled(),
    reason="Marva dancer UI tests require the full stack (Nginx + Marva + DCTap Dancer)",
)

DANCER_WORKSPACE_KEY = "marva-dancerWorkspace"
PROFILE_URL = re.compile(r"/marva/dancer/api/serve/([0-9a-f-]{36})/profile$")


def marva_url() -> str:
    return os.getenv("INTEGRATION_MARVA_BASE_URL", f"{bluecore_url()}/marva").rstrip(
        "/"
    )


class DancerTraffic:
    """Records the dancer requests Marva makes, to see which workspace it loads."""

    def __init__(self, page: Page) -> None:
        self.workspace_list_requested = False
        self.profile_loads: list[tuple[str, int]] = []
        page.on("response", self._on_response)

    def _on_response(self, response: Response) -> None:
        url = response.url.split("?")[0]
        if url.endswith("/marva/dancer/api/serve/workspaces"):
            self.workspace_list_requested = True
        match = PROFILE_URL.search(url)
        if match:
            self.profile_loads.append((match.group(1), response.status))

    def reset(self) -> None:
        self.workspace_list_requested = False
        self.profile_loads.clear()

    def wait_for_profile_load(self, page: Page, timeout: int) -> tuple[str, int]:
        """The (workspace ID, status) of the profile Marva loaded from the dancer."""
        for _ in range(timeout // 250):
            if self.profile_loads:
                return self.profile_loads[-1]
            page.wait_for_timeout(250)
        if not self.workspace_list_requested:
            pytest.skip(
                "This Marva build doesn't load profiles from the DCTap Dancer yet. "
                "Build Marva from a branch (--marva-ref / --dev-mode) to run it."
            )
        raise AssertionError(
            "Marva asked for the dancer's workspaces but never loaded a profile"
        )


def _dismiss_cataloging_code(page: Page) -> None:
    """A new browser has no cataloging code, so Marva asks for one first."""
    code = page.get_by_placeholder("Cataloging Code")
    try:
        code.wait_for(state="visible", timeout=5_000)
    except PlaywrightTimeoutError:
        return
    code.fill("uitest")
    page.get_by_role("button", name="Done").click()
    expect(code).to_be_hidden()


def _login_to_marva(page: Page, timeout: int) -> DancerTraffic:
    """Log into Marva through its middleware and Keycloak, recording dancer traffic."""
    traffic = DancerTraffic(page)
    page.goto(
        f"{marva_url()}/util/auth/login", wait_until="domcontentloaded", timeout=timeout
    )
    submit_keycloak_login(page, timeout)
    page.wait_for_url(f"{marva_url()}/**", timeout=timeout)
    _dismiss_cataloging_code(page)
    return traffic


def _stored_workspace(page: Page) -> str | None:
    return page.evaluate(f"() => window.localStorage.getItem('{DANCER_WORKSPACE_KEY}')")


def _open_dctap_menu(page: Page, timeout: int) -> None:
    menu = page.get_by_text(re.compile(r"^DCTap: "))
    expect(menu.first).to_be_visible(timeout=timeout)
    menu.first.click()


# ========================================================================
# After login, Marva loads its profiles and starting points from the
# dancer's default workspace ("Blue Core") and remembers it as selected.
# ------------------------------------------------------------------------
def test_marva_loads_profiles_from_the_default_workspace(
    page: Page, ui_timeout_ms: int, dancer_api
):
    log_header("Marva loads profiles from the DCTap Dancer")
    seeded_id = dancer_api.seeded_workspace()["id"]
    traffic = _login_to_marva(page, ui_timeout_ms)

    workspace_id, status = traffic.wait_for_profile_load(page, ui_timeout_ms)
    log_expected_actual(
        "profile workspace, status", (seeded_id, 200), (workspace_id, status)
    )
    assert (workspace_id, status) == (seeded_id, 200)
    assert _stored_workspace(page) == seeded_id


# ========================================================================
# The DCTap menu shows the loaded workspace and lists the dancer's
# workspaces, plus the "Edit Templates" link.
# ------------------------------------------------------------------------
def test_dctap_menu_lists_workspaces(page: Page, ui_timeout_ms: int, dancer_api):
    log_header("Marva DCTap menu")
    traffic = _login_to_marva(page, ui_timeout_ms)
    traffic.wait_for_profile_load(page, ui_timeout_ms)

    expect(
        page.get_by_text(f"DCTap: {SEEDED_WORKSPACE[:10]}", exact=True)
    ).to_be_visible(timeout=ui_timeout_ms)
    _open_dctap_menu(page, ui_timeout_ms)
    for workspace in dancer_api.workspaces():
        expect(page.get_by_text(workspace["name"], exact=True).last).to_be_visible()
    expect(
        page.get_by_text("Edit Templates (DCTap Dancer)", exact=True)
    ).to_be_visible()


# ========================================================================
# "Edit Templates" opens the dancer in a new tab, already signed in through
# the same Keycloak session (no second login).
# ------------------------------------------------------------------------
def test_edit_templates_opens_the_dancer_signed_in(page: Page, ui_timeout_ms: int):
    log_header("Marva Edit Templates opens the DCTap Dancer")
    traffic = _login_to_marva(page, ui_timeout_ms)
    traffic.wait_for_profile_load(page, ui_timeout_ms)
    _open_dctap_menu(page, ui_timeout_ms)

    with page.context.expect_page(timeout=ui_timeout_ms) as new_tab_info:
        page.get_by_text("Edit Templates (DCTap Dancer)", exact=True).click()
    dancer = new_tab_info.value
    dancer.wait_for_url(f"{dancer_url()}/**", timeout=ui_timeout_ms)

    expect(dancer.locator(".bluecore-user-bar")).to_be_visible(timeout=ui_timeout_ms)
    log_expected_actual("dancer tab URL", f"{dancer_url()}/", dancer.url)
    assert dancer.url == f"{dancer_url()}/"
    assert KEYCLOAK_AUTH_PATH not in dancer.url


# ========================================================================
# Picking another workspace in the DCTap menu reloads Marva with that
# workspace's profiles.
# ------------------------------------------------------------------------
def test_switching_workspace_loads_its_profiles(
    page: Page, ui_timeout_ms: int, dancer_api
):
    log_header("Marva switches DCTap workspace")
    copy = dancer_api.duplicate(dancer_api.seeded_workspace()["id"])
    traffic = _login_to_marva(page, ui_timeout_ms)
    traffic.wait_for_profile_load(page, ui_timeout_ms)

    _open_dctap_menu(page, ui_timeout_ms)
    traffic.reset()
    page.get_by_text(copy["name"], exact=True).last.click()

    workspace_id, status = traffic.wait_for_profile_load(page, ui_timeout_ms)
    log_expected_actual("profile workspace after switch", copy["id"], workspace_id)
    assert (workspace_id, status) == (copy["id"], 200)
    assert _stored_workspace(page) == copy["id"]


# ========================================================================
# A saved workspace that no longer exists (e.g. after the dancer's data was
# reset) falls back to the default workspace instead of breaking Marva.
# ------------------------------------------------------------------------
def test_stale_workspace_selection_falls_back_to_default(
    page: Page, ui_timeout_ms: int, dancer_api
):
    log_header("Marva falls back from a stale DCTap workspace")
    seeded_id = dancer_api.seeded_workspace()["id"]
    traffic = _login_to_marva(page, ui_timeout_ms)
    traffic.wait_for_profile_load(page, ui_timeout_ms)

    stale_id = "00000000-0000-0000-0000-000000000000"
    page.evaluate(
        f"() => window.localStorage.setItem('{DANCER_WORKSPACE_KEY}', '{stale_id}')"
    )
    traffic.reset()
    page.reload(wait_until="domcontentloaded")

    workspace_id, status = traffic.wait_for_profile_load(page, ui_timeout_ms)
    log_expected_actual("profile workspace after reload", seeded_id, workspace_id)
    assert (workspace_id, status) == (seeded_id, 200)
    assert _stored_workspace(page) == seeded_id
