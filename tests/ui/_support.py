from __future__ import annotations

import os

# Shared configuration for the browser UI tests. Values come from the same
# INTEGRATION_* environment the integration runner already exports, so the UI
# suite needs no extra setup to run alongside the HTTP integration tests.

# Keycloak's realm login endpoint; the marker used to detect the SSO redirect.
KEYCLOAK_AUTH_PATH = "/realms/bluecore/protocol/openid-connect/auth"


def bluecore_url() -> str:
    return os.getenv("INTEGRATION_BLUECORE_URL", "http://localhost").rstrip("/")


def sinopia_url() -> str:
    return os.getenv("INTEGRATION_SINOPIA_BASE_URL", f"{bluecore_url()}/sinopia").rstrip("/")


def keycloak_username() -> str:
    return os.getenv("INTEGRATION_KEYCLOAK_USERNAME", "developer")


def keycloak_password() -> str:
    return os.getenv("INTEGRATION_KEYCLOAK_PASSWORD", "123456")


def ready_timeout() -> int:
    return int(os.getenv("INTEGRATION_READY_TIMEOUT", "300"))


def poll_interval() -> float:
    return float(os.getenv("INTEGRATION_READY_POLL_INTERVAL", "3"))


def full_stack_enabled() -> bool:
    return os.getenv("INTEGRATION_FULL_STACK", "1") == "1"
