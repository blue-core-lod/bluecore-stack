from __future__ import annotations

import time

import pytest
from playwright.sync_api import APIRequestContext, Playwright

from tests.ui._support import full_stack_enabled

# How many records to look through when hunting for a suitable one.
SCAN_LIMIT = 25

# These fixtures find records the stack already holds; they never create any.
# The runner loads the sample batch first, so a tests/ui-only run against an
# empty stack skips the resource tests and says so.


# ==============================================================================
# The API as the browser addresses it -- the Nginx URL, so these tests go
# through the same proxy a real user does.
# ------------------------------------------------------------------------------
@pytest.fixture(scope="session")
def api_base_url(pytestconfig: pytest.Config) -> str:
    return str(pytestconfig.getoption("--integration-base-url")).rstrip("/")


# ==============================================================================
# HTTP client used only to find records; the tests themselves use a browser.
# ------------------------------------------------------------------------------
@pytest.fixture(scope="session")
def api_request_context(playwright: Playwright) -> APIRequestContext:
    context = playwright.request.new_context(ignore_https_errors=True)
    try:
        yield context
    finally:
        context.dispose()


# ==============================================================================
# The first search hit of a type, or None.
# ------------------------------------------------------------------------------
def _first_uuid(
    request_context: APIRequestContext,
    api_base_url: str,
    resource_type: str,
    query: str,
) -> str | None:
    response = request_context.get(
        f"{api_base_url}/search/",
        params={"q": query, "type": resource_type, "limit": 1, "offset": 0},
        timeout=15_000,
    )
    if response.status != 200:
        return None
    results = response.json().get("results") or []
    for item in results:
        if item.get("uuid"):
            return str(item["uuid"])
    return None


def _require_full_stack() -> None:
    if not full_stack_enabled():
        pytest.skip("API view tests require the full stack (Nginx + API)")



# ==============================================================================
# A Work with Instances under it, and an Instance belonging to a Work. Searched
# for rather than taken first, since not every record has those links.
# ------------------------------------------------------------------------------
@pytest.fixture(scope="session")
def seeded_resource_uuids(
    api_request_context: APIRequestContext, api_base_url: str
) -> tuple[str, str]:
    _require_full_stack()

    deadline = time.time() + 30
    while time.time() < deadline:
        work = _scan_rendered(
            api_request_context,
            api_base_url,
            "works",
            lambda html: "Has Instance" in html,
        )
        instance = _scan_rendered(
            api_request_context,
            api_base_url,
            "instances",
            lambda html: "Instance of" in html,
        )
        if work and instance:
            return work, instance
        time.sleep(2)

    pytest.skip(
        "No linked Work/Instance pair found for the resource-view tests. These "
        "run as part of the standard suite, which seeds the sample batch first: "
        "./scripts/test/integration-tests.sh"
    )


# ==============================================================================
# Any Hub in the stack, or a skip when there is none.
# ------------------------------------------------------------------------------
@pytest.fixture(scope="session")
def hub_uuid(api_request_context: APIRequestContext, api_base_url: str) -> str:
    _require_full_stack()

    hub = _first_uuid(api_request_context, api_base_url, "hubs", "")
    if not hub:
        pytest.skip("No Hub in the stack to render; skipping the Hub view tests.")
    return hub


def _scan_rendered(
    request_context: APIRequestContext,
    api_base_url: str,
    resource_type: str,
    matches,
) -> str | None:
    """First record of this type whose page satisfies `matches`.

    Records vary a lot, so looking at only the first one would often skip.
    """
    listing = request_context.get(
        f"{api_base_url}/search/",
        params={"q": "", "type": resource_type, "limit": SCAN_LIMIT, "offset": 0},
        timeout=15_000,
    )
    if listing.status != 200:
        return None

    for item in listing.json().get("results") or []:
        uuid = item.get("uuid")
        if not uuid:
            continue
        rendered = request_context.get(
            f"{api_base_url}/{resource_type}/{uuid}",
            headers={"Accept": "text/html"},
            timeout=15_000,
        )
        if rendered.status == 200 and matches(rendered.text()):
            return str(uuid)
    return None


# ==============================================================================
# A Hub with related records, so there is a sidebar to look at. Many have none.
# ------------------------------------------------------------------------------
@pytest.fixture(scope="session")
def hub_uuid_with_sidebar(
    api_request_context: APIRequestContext, api_base_url: str
) -> str:
    _require_full_stack()

    uuid = _scan_rendered(
        api_request_context, api_base_url, "hubs", lambda html: "bc-sidebar" in html
    )
    if not uuid:
        pytest.skip(
            f"None of the first {SCAN_LIMIT} Hubs has related records, "
            "so no Hub sidebar is rendered to assert against."
        )
    return uuid



# ==============================================================================
# A stub record -- a placeholder the stack knows about but has no description
# for. Any type can be one, so try each in turn.
# ------------------------------------------------------------------------------
@pytest.fixture(scope="session")
def stub_record(api_request_context: APIRequestContext, api_base_url: str) -> tuple[str, str]:
    _require_full_stack()

    for resource_type in ("hubs", "works", "instances"):
        uuid = _scan_rendered(
            api_request_context,
            api_base_url,
            resource_type,
            lambda html: 'class="bc-stub"' in html,
        )
        if uuid:
            return resource_type, uuid

    pytest.skip(f"No stub record among the first {SCAN_LIMIT} of each type.")


# ==============================================================================
# Looks up a uuid by resource_type, so one test can cover all three.
# ------------------------------------------------------------------------------
@pytest.fixture
def resource_uuid_for(
    seeded_resource_uuids: tuple[str, str], request: pytest.FixtureRequest
):
    work_uuid, instance_uuid = seeded_resource_uuids

    def _lookup(resource_type: str) -> str:
        if resource_type == "works":
            return work_uuid
        if resource_type == "instances":
            return instance_uuid
        return request.getfixturevalue("hub_uuid")

    return _lookup
