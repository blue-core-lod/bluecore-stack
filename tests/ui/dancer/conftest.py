from __future__ import annotations

import time
import urllib.error
import urllib.request

import pytest
from playwright.sync_api import Playwright

from tests.ui._support import full_stack_enabled, poll_interval, ready_timeout
from tests.ui.dancer._support import DancerApi
from tests.integration.dancer._support import dancer_api_url


# ==============================================================================
# Block the dancer UI suite until the dancer answers through Nginx. On a fresh
# stack it seeds the "Blue Core" workspace before it starts listening.
# ------------------------------------------------------------------------------
@pytest.fixture(scope="session", autouse=True)
def wait_for_dancer_ui() -> None:
    if not full_stack_enabled():
        return
    url = f"{dancer_api_url()}/health"
    deadline = time.time() + ready_timeout()
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=10) as response:  # noqa: S310
                if response.status == 200:
                    return
        except (urllib.error.URLError, OSError) as exc:
            last_error = exc
        time.sleep(poll_interval())
    raise AssertionError(
        f"Timed out waiting for the DCTap Dancer at {url}. Last error: {last_error!r}."
    )


# ==============================================================================
# Direct API access for setup/cleanup. Workspaces a test creates through it
# (or registers with track()) are deleted after the test.
# ------------------------------------------------------------------------------
@pytest.fixture
def dancer_api(playwright: Playwright):
    request = playwright.request.new_context()
    api = DancerApi(request)
    try:
        yield api
    finally:
        api.cleanup()
        request.dispose()
