from __future__ import annotations

import pytest

from tests.ui._support import bluecore_url


# ==============================================================================
# The Nginx root, not a service prefix -- the landing page is the gateway's own
# page and every link on it is relative to that root.
# ------------------------------------------------------------------------------
@pytest.fixture(scope="session")
def landing_base_url() -> str:
    return bluecore_url()
