from __future__ import annotations

import os
import secrets
import string

# The DCTap Dancer is Marva's profile/template editor, served through Nginx at
# /marva/dancer/. Its /api/serve/ routes are public (Marva reads profiles from
# them); everything else under /api/ needs a Keycloak token.

# The workspace the stack seeds on first start and Blue Core Marva loads by default.
SEEDED_WORKSPACE = os.getenv("INTEGRATION_DANCER_SEED_WORKSPACE", "Blue Core")

# Keycloak client the dancer's frontend logs in with.
DANCER_CLIENT_ID = "bluecore_api"


def bluecore_url() -> str:
    return os.getenv("INTEGRATION_BLUECORE_URL", "http://localhost").rstrip("/")


def dancer_url() -> str:
    return os.getenv(
        "INTEGRATION_DANCER_BASE_URL", f"{bluecore_url()}/marva/dancer"
    ).rstrip("/")


def dancer_api_url() -> str:
    return f"{dancer_url()}/api"


def keycloak_url() -> str:
    return os.getenv(
        "INTEGRATION_KEYCLOAK_PUBLIC_URL", f"{bluecore_url()}/keycloak"
    ).rstrip("/")


def slugify(name: str) -> str:
    """The dancer's alias for a workspace name in /api/serve/<alias>/... URLs."""
    slug = "".join(ch if ch.isalnum() else "-" for ch in name.lower().strip())
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-")


def temp_workspace_name() -> str:
    """A unique, recognizable name for a workspace a test creates and deletes."""
    suffix = "".join(secrets.choice(string.ascii_lowercase) for _ in range(8))
    return f"integration test {suffix}"


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
