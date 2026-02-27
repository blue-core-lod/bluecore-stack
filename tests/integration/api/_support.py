from __future__ import annotations

import json


# ========================================================================
# Check whether serialized payload contains an expected text fragment.
# ------------------------------------------------------------------------
def payload_contains_text(payload: object, text: str) -> bool:
    return text in json.dumps(payload, sort_keys=True)


# ========================================================================
# Assert multiple expected text fragments are present in a payload.
# ------------------------------------------------------------------------
def assert_payload_contains(payload: object, expectations: dict[str, str]) -> None:
    for label, expected_text in expectations.items():
        assert payload_contains_text(payload, expected_text), (
            f"Payload missing expected {label}: {expected_text}"
        )
