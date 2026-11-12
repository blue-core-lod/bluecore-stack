from __future__ import annotations

import os
import re

from playwright.sync_api import APIRequestContext, Locator, Page, expect

from tests.integration.dancer._support import (
    SEEDED_WORKSPACE,
    dancer_api_url,
    dancer_url,
    temp_workspace_name,
)
from tests.ui._support import (
    KEYCLOAK_AUTH_PATH,
    bluecore_url,
    keycloak_password,
    keycloak_username,
)

# Shared by the dancer UI suite (tests/ui/dancer) and the Marva-side dancer
# tests (tests/ui/marva/test_dancer.py).

__all__ = [
    "SEEDED_WORKSPACE",
    "DancerApi",
    "dancer_url",
    "login_to_dancer",
    "submit_keycloak_login",
    "temp_workspace_name",
    "workspace_card",
]


def keycloak_token_url() -> str:
    return os.getenv(
        "INTEGRATION_KEYCLOAK_TOKEN_URL",
        f"{bluecore_url()}/keycloak/realms/bluecore/protocol/openid-connect/token",
    )


def submit_keycloak_login(page: Page, timeout: int) -> None:
    """Fill in and submit the Keycloak login form the page is sitting on."""
    page.wait_for_url(f"**{KEYCLOAK_AUTH_PATH}**", timeout=timeout)
    page.locator("#username").fill(keycloak_username())
    page.locator("#password").fill(keycloak_password())
    page.locator("#kc-login").click()


def login_to_dancer(page: Page, timeout: int, path: str = "/") -> None:
    """
    Open a dancer page logged out, log in through Keycloak, and wait until the
    editor is back with the "Signed in as …" bar showing.
    """
    page.goto(f"{dancer_url()}{path}", wait_until="domcontentloaded", timeout=timeout)
    submit_keycloak_login(page, timeout)
    page.wait_for_url(f"{dancer_url()}/**", timeout=timeout)
    expect(page.locator(".bluecore-user-bar")).to_be_visible(timeout=timeout)


def workspace_card(page: Page, name: str) -> Locator:
    """The home page card for the workspace with exactly this name."""
    title = page.locator(
        ".workspace-name", has_text=re.compile(rf"^\W*{re.escape(name)}\W*$")
    )
    return page.locator(".workspace-card", has=title)


class DancerApi:
    """
    Talks to the dancer API directly (as the test user) to look up workspaces
    and to create/delete the temporary ones tests use. Every workspace it
    creates is deleted again by cleanup(), so tests never touch real data.
    """

    def __init__(self, request: APIRequestContext) -> None:
        self._request = request
        self._created: list[str] = []

    def _token(self) -> str:
        response = self._request.post(
            keycloak_token_url(),
            form={
                "grant_type": "password",
                "client_id": "bluecore_api",
                "username": keycloak_username(),
                "password": keycloak_password(),
            },
            fail_on_status_code=False,
        )
        assert response.status == 200, (
            f"Keycloak token request failed: {response.status}"
        )
        return response.json()["access_token"]

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token()}"}

    def workspaces(self) -> list[dict]:
        response = self._request.get(f"{dancer_api_url()}/serve/workspaces")
        assert response.status == 200
        return response.json()["data"]

    def find(self, name: str) -> dict | None:
        return next((ws for ws in self.workspaces() if ws["name"] == name), None)

    def seeded_workspace(self) -> dict:
        workspace = self.find(SEEDED_WORKSPACE)
        assert workspace is not None, (
            f"No '{SEEDED_WORKSPACE}' workspace; did seeding fail?"
        )
        return workspace

    def track(self, workspace_id: str) -> str:
        """Delete this workspace at cleanup (e.g. one a test created in the UI)."""
        self._created.append(workspace_id)
        return workspace_id

    def create(self, name: str | None = None) -> dict:
        name = name or temp_workspace_name()
        response = self._request.post(
            f"{dancer_api_url()}/workspaces",
            headers=self._headers(),
            data={"name": name},
            fail_on_status_code=False,
        )
        assert response.status == 201, f"Creating workspace failed: {response.status}"
        workspace = response.json()["data"]
        self.track(workspace["id"])
        return workspace

    def duplicate(self, source_id: str, name: str | None = None) -> dict:
        name = name or temp_workspace_name()
        response = self._request.post(
            f"{dancer_api_url()}/workspaces/{source_id}/duplicate",
            headers=self._headers(),
            data={"name": name},
            fail_on_status_code=False,
        )
        assert response.status == 201, (
            f"Duplicating workspace failed: {response.status}"
        )
        workspace = response.json()["data"]
        self.track(workspace["id"])
        return workspace

    def cleanup(self) -> None:
        for workspace_id in reversed(self._created):
            self._request.delete(
                f"{dancer_api_url()}/workspaces/{workspace_id}",
                headers=self._headers(),
                fail_on_status_code=False,
            )
        self._created.clear()
