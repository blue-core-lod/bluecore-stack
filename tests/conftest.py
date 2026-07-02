from __future__ import annotations

import os

import pytest


# ==============================================================================
# Register custom pytest options shared by the integration and UI test trees.
#
# Defined here (a parent of both tests/integration and tests/ui) so the options
# are registered no matter which subtree a run targets. The integration runner
# always passes --integration-base-url, so a tests/ui-only run must still
# recognize it even though it never loads tests/integration/conftest.py.
# ------------------------------------------------------------------------------
def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--integration-base-url",
        action="store",
        default=os.getenv("INTEGRATION_BASE_URL", "http://localhost:18100"),
        help="Base URL for the API service under test.",
    )
    parser.addoption(
        "--integration-ready-timeout",
        action="store",
        type=int,
        default=int(os.getenv("INTEGRATION_READY_TIMEOUT", "300")),
        help="Seconds to wait for stack readiness checks.",
    )
