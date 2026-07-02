from __future__ import annotations

import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

import pytest

from tests.ui._support import (
    bluecore_url,
    full_stack_enabled,
    poll_interval,
    ready_timeout,
    sinopia_url,
)

# Browser fixtures (page/context/browser) come from the installed
# pytest-playwright plugin; this conftest only adds a readiness gate so the UI
# suite waits for the Sinopia route before driving it. No pytest options are
# registered here, so the UI suite composes cleanly with tests/integration in a
# single pytest run.


# ==============================================================================
# Block the UI suite until the Sinopia editor route is served through Nginx.
# Only runs when a full-stack (Nginx + Sinopia) run is active; lightweight runs
# skip the UI tests, so this never fires there.
# ------------------------------------------------------------------------------
@pytest.fixture(scope="session", autouse=True)
def wait_for_sinopia_ui() -> None:
    if not full_stack_enabled():
        return

    url = f"{sinopia_url()}/"
    deadline = time.time() + ready_timeout()
    last_error: Exception | None = None

    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=10) as response:  # noqa: S310
                if response.status == 200:
                    return
        except urllib.error.HTTPError as exc:
            # Any non-5xx means Nginx/Sinopia are answering.
            if exc.code < 500:
                return
            last_error = exc
        except Exception as exc:  # noqa: BLE001
            last_error = exc
        time.sleep(poll_interval())

    raise AssertionError(
        f"Timed out waiting for the Sinopia UI at {url}. Last error: {last_error!r}."
    )


# ==============================================================================
# Give the editor's SPA enough time to boot and complete SSO redirects.
# ------------------------------------------------------------------------------
@pytest.fixture(scope="session")
def ui_timeout_ms() -> int:
    return 30_000


# Uncaught browser errors that are benign noise rather than app regressions.
# Extend with SINOPIA_UI_IGNORE_ERRORS (comma-separated substrings).
_DEFAULT_IGNORED_ERRORS = ("ResizeObserver loop",)


def _ignored_error_patterns() -> tuple[str, ...]:
    extra = os.getenv("SINOPIA_UI_IGNORE_ERRORS", "")
    return _DEFAULT_IGNORED_ERRORS + tuple(p for p in (s.strip() for s in extra.split(",")) if p)


@dataclass
class PageSignals:
    """Collects uncaught JS errors and same-origin server (5xx) responses."""

    page_errors: list[str] = field(default_factory=list)
    server_errors: list[str] = field(default_factory=list)


# ==============================================================================
# Attach listeners (before navigation) that record uncaught JS exceptions and
# same-origin 5xx responses, so a test can assert the editor loaded cleanly.
# ------------------------------------------------------------------------------
@pytest.fixture
def page_signals(page) -> PageSignals:
    signals = PageSignals()
    ignored = _ignored_error_patterns()
    local_origin = bluecore_url()

    def _on_page_error(exc) -> None:
        message = str(exc)
        if not any(pattern in message for pattern in ignored):
            signals.page_errors.append(message)

    def _on_response(response) -> None:
        try:
            url = response.url
            if response.status >= 500 and (
                url.startswith(local_origin) or "localhost" in url
            ):
                signals.server_errors.append(f"{response.status} {url}")
        except Exception:  # noqa: BLE001 - never let logging break a test
            pass

    page.on("pageerror", _on_page_error)
    page.on("response", _on_response)
    return signals
