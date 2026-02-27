from __future__ import annotations

import json


# ========================================================================
# Wrap text with ANSI color codes for readable test console output.
# ------------------------------------------------------------------------
def color(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m"


# ========================================================================
# Print standardized section headers for integration test phases.
# ------------------------------------------------------------------------
def log_header(title: str) -> None:
    print("\n", flush=True)
    print(color("=" * 88, "2;37"), flush=True)
    print(color(f"🧪 {title}", "1;36"), flush=True)
    print(color("=" * 88, "2;37"), flush=True)


# ========================================================================
# Print expected/actual values in a consistent assertion log format.
# ------------------------------------------------------------------------
def log_expected_actual(label: str, expected, actual) -> None:
    print(color(f"Expected {label}: {expected}", "1;33"), flush=True)
    print(color(f"Actual   {label}: {actual}", "1;32"), flush=True)


# ========================================================================
# Print dictionary payloads as formatted JSON for debug visibility.
# ------------------------------------------------------------------------
def log_json(label: str, payload: dict) -> None:
    pretty = json.dumps(payload, indent=2, sort_keys=True)
    print(color(f"{label}:", "1;35"), flush=True)
    print(pretty, flush=True)
