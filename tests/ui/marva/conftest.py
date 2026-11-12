from __future__ import annotations

# Marva's DCTap Dancer tests (test_dancer.py) reuse the dancer suite's API
# helper and readiness gate. The gate only waits when the full stack runs.
from tests.ui.dancer.conftest import dancer_api, wait_for_dancer_ui  # noqa: F401
